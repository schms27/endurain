<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { FolderSync, LoaderCircle } from '@lucide/vue'

import type { AutoImportSettingsInput } from '@/features/import/types'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useToasts } from '@/composables/useToasts'
import { HttpError } from '@/services/http'
import { formatRelativeTime } from '@/utils/datetime'
import { AUTO_IMPORT_INTERVALS } from '@/features/import/types'
import {
  useAutoImportSettingsQuery,
  useRunAutoImportMutation,
  useUpdateAutoImportSettingsMutation,
} from '@/features/import/composables/useImport'

const { t, locale } = useI18n()
const toasts = useToasts()

const settingsQuery = useAutoImportSettingsQuery()
const updateSettings = useUpdateAutoImportSettingsMutation()
const runNow = useRunAutoImportMutation()

const settings = computed(() => settingsQuery.data.value)
const busy = computed(() => updateSettings.isPending.value || !settings.value)

function save(input: AutoImportSettingsInput): void {
  updateSettings.mutate(input, {
    onError: () => toasts.error(t('settings.import.auto.saveError')),
  })
}

const enabled = computed<boolean>({
  get: () => settings.value?.enabled ?? false,
  set: (value) => {
    if (settings.value) {
      save({ enabled: value, intervalMinutes: settings.value.intervalMinutes })
    }
  },
})

const intervalMinutes = computed<number>({
  get: () => settings.value?.intervalMinutes ?? 60,
  set: (value) => {
    if (settings.value) {
      save({ enabled: settings.value.enabled, intervalMinutes: Number(value) })
    }
  },
})

const lastRun = computed(() => {
  const current = settings.value
  if (!current?.lastRunAt) {
    return t('settings.import.auto.neverRun')
  }
  return t('settings.import.auto.lastRun', {
    when: formatRelativeTime(current.lastRunAt, new Date(), locale.value),
    imported: current.lastRunImported,
    failed: current.lastRunFailed,
  })
})

function onRunNow(): void {
  runNow.mutate(undefined, {
    onSuccess: () => {
      toasts.info(t('settings.import.auto.started'))
      // The scan runs in the background; refresh the status once it has had time to finish.
      setTimeout(() => void settingsQuery.refetch(), 5000)
    },
    onError: (error) =>
      toasts.error(
        error instanceof HttpError && error.status === 409
          ? t('settings.import.auto.alreadyRunning')
          : t('settings.import.auto.runError'),
      ),
  })
}
</script>

<template>
  <Card class="flex flex-col gap-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex min-w-0 items-center gap-3">
        <div
          class="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted-foreground/15 text-muted-foreground"
        >
          <FolderSync class="size-5" aria-hidden="true" />
        </div>
        <div class="min-w-0">
          <h2 class="text-card-heading">{{ t('settings.import.auto.title') }}</h2>
          <p class="text-hint">{{ t('settings.import.auto.subtitle') }}</p>
        </div>
      </div>

      <Switch v-model="enabled" :disabled="busy" :aria-label="t('settings.import.auto.enable')" />
    </div>

    <div v-if="settings" class="flex flex-col gap-3">
      <p class="text-body">
        {{ t('settings.import.auto.folderHint') }}
        <code class="break-all rounded bg-muted px-1 py-0.5 text-sm">{{ settings.folder }}</code>
      </p>

      <div class="flex flex-wrap items-center gap-3">
        <label for="auto-import-interval" class="text-body">
          {{ t('settings.import.auto.interval') }}
        </label>
        <Select
          id="auto-import-interval"
          v-model="intervalMinutes"
          class="w-auto"
          :disabled="busy || !settings.enabled"
        >
          <option v-for="minutes in AUTO_IMPORT_INTERVALS" :key="minutes" :value="minutes">
            {{ t(`settings.import.auto.intervals.${minutes}`) }}
          </option>
        </Select>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="text-hint flex flex-col">
          <span>{{ lastRun }}</span>
          <span>{{ t('settings.import.auto.pending', { count: settings.pendingFiles }) }}</span>
        </div>
        <Button size="sm" variant="outline" :disabled="runNow.isPending.value" @click="onRunNow">
          <LoaderCircle
            v-if="runNow.isPending.value"
            class="size-4 animate-spin"
            aria-hidden="true"
          />
          {{ t('settings.import.auto.runNow') }}
        </Button>
      </div>
    </div>
  </Card>
</template>
