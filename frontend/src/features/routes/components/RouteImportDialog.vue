<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileUp } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { FormDialog } from '@/components/ui/form-dialog'
import { useImportRouteMutation } from '@/features/routes/composables/useRoutes'
import {
  assertValidRouteFile,
  RouteFileValidationError,
  type RouteFileProblem,
} from '@/features/routes/services/routes'
import { ROUTE_FILE_ACCEPT } from '@/features/routes/types'

const PROBLEM_KEYS = {
  empty: 'routes.import.problem.empty',
  extension: 'routes.import.problem.extension',
  size: 'routes.import.problem.size',
} as const satisfies Record<RouteFileProblem, string>

const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{
  /** One message per finished import run (success summary). */
  success: [message: string]
  /** One message per file that failed. */
  error: [message: string]
}>()

const { t } = useI18n()
const importMutation = useImportRouteMutation()

const fileInput = ref<HTMLInputElement | null>(null)
const files = ref<File[]>([])
const current = ref(0)
const isImporting = ref(false)

/** Problem description for a file that fails the client-side checks. */
function problemFor(file: File): string | null {
  try {
    assertValidRouteFile(file)
    return null
  } catch (err) {
    return err instanceof RouteFileValidationError ? t(PROBLEM_KEYS[err.problem]) : null
  }
}

const rows = computed(() => files.value.map((file) => ({ file, problem: problemFor(file) })))
const importable = computed(() =>
  rows.value.filter((row) => row.problem === null).map((row) => row.file),
)

function chooseFiles(): void {
  fileInput.value?.click()
}

function onFilesSelected(event: Event): void {
  const input = event.target as HTMLInputElement
  files.value = Array.from(input.files ?? [])
  input.value = ''
}

/** Imports the valid files one by one, reporting each failure. */
async function runImport(): Promise<void> {
  const queue = importable.value
  isImporting.value = true
  let imported = 0
  for (const [index, file] of queue.entries()) {
    current.value = index + 1
    try {
      await importMutation.mutateAsync(file)
      imported += 1
    } catch {
      emit('error', t('routes.import.failed', { name: file.name }))
    }
  }
  isImporting.value = false
  if (imported > 0) {
    emit('success', t('routes.import.success', { count: imported }, imported))
  }
  open.value = false
}

watch(open, (isOpen) => {
  if (isOpen) {
    files.value = []
    current.value = 0
  }
})
</script>

<template>
  <FormDialog
    v-model:open="open"
    :title="t('routes.import.title')"
    :description="t('routes.import.description')"
    :submit-label="t('routes.import.start')"
    :cancel-label="t('routes.import.cancel')"
    :close-label="t('routes.import.close')"
    :submitting="isImporting"
    :can-submit="importable.length > 0"
    @submit="runImport"
  >
    <div class="flex flex-col gap-3">
      <Button type="button" variant="outline" :disabled="isImporting" @click="chooseFiles">
        <FileUp class="size-4" aria-hidden="true" />
        {{ t('routes.import.choose') }}
      </Button>
      <p class="text-hint">{{ t('routes.import.accepted') }}</p>
      <input
        ref="fileInput"
        type="file"
        multiple
        :accept="ROUTE_FILE_ACCEPT"
        class="hidden"
        data-testid="route-file-input"
        @change="onFilesSelected"
      />
      <ul v-if="rows.length > 0" class="divide-y divide-border rounded-input border border-border">
        <li
          v-for="row in rows"
          :key="row.file.name"
          class="flex items-center justify-between gap-3 px-3 py-2"
        >
          <span class="truncate text-body">{{ row.file.name }}</span>
          <span v-if="row.problem" class="shrink-0 text-hint text-destructive">{{
            row.problem
          }}</span>
        </li>
      </ul>
      <p v-if="isImporting" class="text-hint" aria-live="polite">
        {{ t('routes.import.progress', { current, total: importable.length }) }}
      </p>
    </div>
  </FormDialog>
</template>
