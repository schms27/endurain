<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import type { GeoPoint, MapOverlay } from '@/composables/useMapProvider'
import type { Units } from '@/features/activities/utils/format'
import type { SegmentSlice } from '@/features/segments/services/segments'
import type { SegmentVisibility, SportGroup } from '@/features/segments/types'
import type { IndexedPoint } from '@/features/segments/utils/segments'

import ActivityMap from '@/features/activities/components/ActivityMap.vue'
import { Alert } from '@/components/ui/alert'
import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { inputFieldClass } from '@/components/ui/input/fieldClasses'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useForm } from '@/composables/useForm'
import { combineMetric, formatDistance } from '@/features/activities/utils/format'
import { useIsAdmin } from '@/features/auth/composables/useCurrentUser'
import {
  useCreateSegmentMutation,
  useSegmentsSettings,
  useSimilarSegmentsQuery,
} from '@/features/segments/composables/useSegments'
import { SEGMENT_VISIBILITY } from '@/features/segments/types'
import { cumulativeDistances, sliceProblem } from '@/features/segments/utils/segments'

/** Pause after the last slider move before checking for duplicates. */
const SIMILAR_DEBOUNCE_MS = 400

const open = defineModel<boolean>('open', { required: true })
const props = defineProps<{
  /** The source activity (must be the viewer's own). */
  activityId: number
  /** Its activity type, for distance formatting. */
  activityType: number
  /** Its sport group (decides the minimum length). */
  sportGroup: SportGroup
  /** The activity's GPS track with stream indices. */
  track: IndexedPoint[]
  /** The viewer's unit system. */
  units: Units
}>()
const emit = defineEmits<{ success: [message: string]; error: [message: string] }>()

const { t } = useI18n()
const isAdmin = useIsAdmin()
const { publicCreationAdminsOnly } = useSegmentsSettings()
const createMutation = useCreateSegmentMutation()

const canPublish = computed(() => isAdmin.value || !publicCreationAdminsOnly.value)
const lastPosition = computed(() => Math.max(0, props.track.length - 1))
const distances = computed(() => cumulativeDistances(props.track))

// Slider positions into `track` (not stream indices: points without GPS are
// already skipped, so every position is a real coordinate).
const startPosition = ref(0)
const endPosition = ref(0)

function onStartInput(event: Event): void {
  const value = Number((event.target as HTMLInputElement).value)
  startPosition.value = Math.min(value, endPosition.value - 1)
}

function onEndInput(event: Event): void {
  const value = Number((event.target as HTMLInputElement).value)
  endPosition.value = Math.max(value, startPosition.value + 1)
}

const startDistance = computed(() => distances.value[startPosition.value] ?? 0)
const endDistance = computed(() => distances.value[endPosition.value] ?? 0)
const sliceDistance = computed(() => endDistance.value - startDistance.value)
const slicePointCount = computed(() => endPosition.value - startPosition.value + 1)
const problem = computed(() =>
  sliceProblem(slicePointCount.value, sliceDistance.value, props.sportGroup),
)

function distanceLabel(meters: number): string {
  return combineMetric(formatDistance(meters, props.activityType, props.units))
}

const fullTrack = computed<GeoPoint[]>(() => props.track.map(({ lat, lng }) => ({ lat, lng })))
const overlays = computed<MapOverlay[]>(() => [
  {
    id: 'proposed-segment',
    points: fullTrack.value.slice(startPosition.value, endPosition.value + 1),
    style: 'highlight',
  },
])

const currentSlice = computed<SegmentSlice | null>(() => {
  const start = props.track[startPosition.value]
  const end = props.track[endPosition.value]
  if (!start || !end || problem.value) {
    return null
  }
  return { activityId: props.activityId, startIndex: start.index, endIndex: end.index }
})

// Only ask the server once the user stops dragging.
const checkedSlice = ref<SegmentSlice | null>(null)
let debounce: ReturnType<typeof setTimeout> | undefined
watch(currentSlice, (slice) => {
  clearTimeout(debounce)
  checkedSlice.value = null
  if (slice && open.value) {
    debounce = setTimeout(() => {
      checkedSlice.value = slice
    }, SIMILAR_DEBOUNCE_MS)
  }
})
onBeforeUnmount(() => clearTimeout(debounce))
const { data: similar } = useSimilarSegmentsQuery(checkedSlice)

interface SegmentFormValues {
  name: string
  description: string
  visibility: SegmentVisibility
}

const { values, isSubmitting, handleSubmit, reset } = useForm<SegmentFormValues>({
  initialValues: { name: '', description: '', visibility: SEGMENT_VISIBILITY.public },
  onSubmit: async (formValues) => {
    const slice = currentSlice.value
    if (!slice) {
      return
    }
    try {
      await createMutation.mutateAsync({
        ...slice,
        name: formValues.name.trim(),
        description: formValues.description.trim() || null,
        visibility: formValues.visibility,
      })
      emit('success', t('segments.create.success'))
      open.value = false
    } catch {
      emit('error', t('segments.create.error'))
    }
  },
})

const canSubmit = computed(() => values.name.trim().length > 0 && currentSlice.value !== null)

// Re-seed each time the dialog opens: the whole activity, public if allowed.
watch(open, (isOpen) => {
  if (!isOpen) {
    clearTimeout(debounce)
    checkedSlice.value = null
    return
  }
  reset()
  values.visibility = canPublish.value ? SEGMENT_VISIBILITY.public : SEGMENT_VISIBILITY.private
  startPosition.value = 0
  endPosition.value = lastPosition.value
})
</script>

<template>
  <FormDialog
    v-model:open="open"
    :title="t('segments.create.title')"
    :description="t('segments.create.description')"
    :submit-label="t('segments.create.save')"
    :cancel-label="t('segments.create.cancel')"
    :close-label="t('segments.create.close')"
    :submitting="isSubmitting"
    :can-submit="canSubmit"
    content-class="sm:max-w-2xl"
    @submit="handleSubmit"
  >
    <div class="flex flex-col gap-3">
      <div class="h-56 overflow-hidden rounded-input">
        <ActivityMap :points="fullTrack" :overlays="overlays" />
      </div>

      <div class="flex flex-col gap-2">
        <div class="flex flex-col gap-1">
          <Label for="segment-start">{{ t('segments.create.start') }}</Label>
          <input
            id="segment-start"
            type="range"
            class="w-full accent-effort"
            min="0"
            :max="lastPosition"
            :value="startPosition"
            :aria-valuetext="distanceLabel(startDistance)"
            :disabled="isSubmitting"
            @input="onStartInput"
          />
        </div>
        <div class="flex flex-col gap-1">
          <Label for="segment-end">{{ t('segments.create.end') }}</Label>
          <input
            id="segment-end"
            type="range"
            class="w-full accent-effort"
            min="0"
            :max="lastPosition"
            :value="endPosition"
            :aria-valuetext="distanceLabel(endDistance)"
            :disabled="isSubmitting"
            @input="onEndInput"
          />
        </div>
        <p class="text-body tabular-nums" aria-live="polite">
          {{
            t('segments.create.range', {
              from: distanceLabel(startDistance),
              to: distanceLabel(endDistance),
              length: distanceLabel(sliceDistance),
            })
          }}
        </p>
        <Alert v-if="problem" kind="warning">{{ t(`segments.create.problem.${problem}`) }}</Alert>
        <Alert v-else-if="similar && similar.length > 0" kind="info">
          {{ t('segments.create.similar') }}
          <ul class="mt-1 list-disc pl-5">
            <li v-for="segment in similar" :key="segment.id">
              <RouterLink :to="{ name: 'segment', params: { id: segment.id } }" class="underline">
                {{ segment.name }}
              </RouterLink>
            </li>
          </ul>
        </Alert>
      </div>

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
            rows="3"
            :disabled="isSubmitting"
          />
        </template>
      </FormField>
      <FormField
        :label="t('segments.visibility.label')"
        :hint="canPublish ? t('segments.visibility.hint') : t('segments.visibility.adminsOnly')"
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
