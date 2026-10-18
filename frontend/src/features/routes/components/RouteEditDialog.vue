<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { RouteDetail } from '@/features/routes/types'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { inputFieldClass } from '@/components/ui/input/fieldClasses'
import { useForm } from '@/composables/useForm'
import { useUpdateRouteMutation } from '@/features/routes/composables/useRoutes'

const open = defineModel<boolean>('open', { required: true })
const props = defineProps<{ route: RouteDetail }>()
const emit = defineEmits<{ success: [message: string]; error: [message: string] }>()

const { t } = useI18n()
const updateMutation = useUpdateRouteMutation()

interface RouteFormValues {
  name: string
  description: string
}

const { values, isSubmitting, handleSubmit, reset } = useForm<RouteFormValues>({
  initialValues: { name: '', description: '' },
  onSubmit: async (formValues) => {
    try {
      await updateMutation.mutateAsync({
        id: props.route.id,
        input: {
          name: formValues.name.trim(),
          description: formValues.description.trim() || null,
        },
      })
      emit('success', t('routes.edit.success'))
      open.value = false
    } catch {
      emit('error', t('routes.edit.error'))
    }
  },
})

const canSubmit = computed(() => values.name.trim().length > 0)

// Re-seed from the route each time the dialog opens.
watch(open, (isOpen) => {
  if (isOpen) {
    reset()
    values.name = props.route.name
    values.description = props.route.description ?? ''
  }
})
</script>

<template>
  <FormDialog
    v-model:open="open"
    :title="t('routes.edit.title')"
    :submit-label="t('routes.edit.save')"
    :cancel-label="t('routes.edit.cancel')"
    :close-label="t('routes.edit.close')"
    :submitting="isSubmitting"
    :can-submit="canSubmit"
    @submit="handleSubmit"
  >
    <div class="flex flex-col gap-3">
      <FormField :label="t('routes.edit.name')" required>
        <template #default="{ fieldId }">
          <Input
            :id="fieldId"
            v-model="values.name"
            maxlength="250"
            :disabled="isSubmitting"
            class="w-full"
          />
        </template>
      </FormField>
      <FormField :label="t('routes.edit.description')">
        <template #default="{ fieldId }">
          <textarea
            :id="fieldId"
            v-model="values.description"
            :class="inputFieldClass"
            maxlength="2500"
            rows="4"
            :disabled="isSubmitting"
          />
        </template>
      </FormField>
    </div>
  </FormDialog>
</template>
