<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { SegmentDetail, SegmentVisibility } from '@/features/segments/types'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { inputFieldClass } from '@/components/ui/input/fieldClasses'
import { Select } from '@/components/ui/select'
import { useForm } from '@/composables/useForm'
import { useIsAdmin } from '@/features/auth/composables/useCurrentUser'
import {
  useSegmentsSettings,
  useUpdateSegmentMutation,
} from '@/features/segments/composables/useSegments'
import { SEGMENT_VISIBILITY } from '@/features/segments/types'

const open = defineModel<boolean>('open', { required: true })
const props = defineProps<{ segment: SegmentDetail }>()
const emit = defineEmits<{ success: [message: string]; error: [message: string] }>()

const { t } = useI18n()
const isAdmin = useIsAdmin()
const { publicCreationAdminsOnly } = useSegmentsSettings()
const updateMutation = useUpdateSegmentMutation()

// Keeping an already public segment public is always allowed.
const canPublish = computed(
  () =>
    isAdmin.value ||
    !publicCreationAdminsOnly.value ||
    props.segment.visibility === SEGMENT_VISIBILITY.public,
)

interface SegmentFormValues {
  name: string
  description: string
  visibility: SegmentVisibility
}

const { values, isSubmitting, handleSubmit, reset } = useForm<SegmentFormValues>({
  initialValues: { name: '', description: '', visibility: SEGMENT_VISIBILITY.public },
  onSubmit: async (formValues) => {
    try {
      await updateMutation.mutateAsync({
        id: props.segment.id,
        input: {
          name: formValues.name.trim(),
          description: formValues.description.trim() || null,
          visibility: formValues.visibility,
        },
      })
      emit('success', t('segments.edit.success'))
      open.value = false
    } catch {
      emit('error', t('segments.edit.error'))
    }
  },
})

const canSubmit = computed(() => values.name.trim().length > 0)
const visibilityChanged = computed(() => values.visibility !== props.segment.visibility)

// Re-seed from the segment each time the dialog opens.
watch(open, (isOpen) => {
  if (isOpen) {
    reset()
    values.name = props.segment.name
    values.description = props.segment.description ?? ''
    values.visibility =
      props.segment.visibility === SEGMENT_VISIBILITY.private
        ? SEGMENT_VISIBILITY.private
        : SEGMENT_VISIBILITY.public
  }
})
</script>

<template>
  <FormDialog
    v-model:open="open"
    :title="t('segments.edit.title')"
    :submit-label="t('segments.edit.save')"
    :cancel-label="t('segments.edit.cancel')"
    :close-label="t('segments.edit.close')"
    :submitting="isSubmitting"
    :can-submit="canSubmit"
    @submit="handleSubmit"
  >
    <div class="flex flex-col gap-3">
      <FormField :label="t('segments.create.name')" required>
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
      <FormField :label="t('segments.create.descriptionLabel')">
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
      <FormField
        :label="t('segments.visibility.label')"
        :hint="visibilityChanged ? t('segments.edit.visibilityRematch') : undefined"
      >
        <template #default="{ fieldId }">
          <Select :id="fieldId" v-model="values.visibility" :disabled="isSubmitting">
            <option :value="SEGMENT_VISIBILITY.public" :disabled="!canPublish">
              {{ t('segments.visibility.public') }}
            </option>
            <option :value="SEGMENT_VISIBILITY.private">
              {{ t('segments.visibility.private') }}
            </option>
          </Select>
        </template>
      </FormField>
    </div>
  </FormDialog>
</template>
