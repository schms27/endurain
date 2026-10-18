<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { Eye, EyeOff, Flag, Plus } from '@lucide/vue'

import type { MapOverlay } from '@/composables/useMapProvider'
import type { Activity } from '@/features/activities/types'
import type { Units } from '@/features/activities/utils/format'
import type { SegmentEffort } from '@/features/segments/types'
import type { IndexedPoint } from '@/features/segments/utils/segments'

import SegmentCreateDialog from '@/features/segments/components/SegmentCreateDialog.vue'
import SegmentMedal from '@/features/segments/components/SegmentMedal.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useToasts } from '@/composables/useToasts'
import { formatHmsDuration } from '@/features/activities/utils/format'
import {
  useActivitySegmentEffortsQuery,
  useSegmentsSettings,
  useSetEffortExcludedMutation,
} from '@/features/segments/composables/useSegments'
import { MIN_SEGMENT_POINTS } from '@/features/segments/types'
import {
  formatEffortSpeed,
  formatTimeDelta,
  sliceTrack,
  sportGroupOf,
} from '@/features/segments/utils/segments'

const props = defineProps<{
  /** The activity whose efforts are listed. */
  activity: Activity
  /** Its GPS track with stream indices (empty when hidden or missing). */
  track: IndexedPoint[]
  /** The viewer's unit system. */
  units: Units
  /** Whether the viewer owns the activity (create, exclude, ranks). */
  isOwner: boolean
}>()
const emit = defineEmits<{
  /** The segment the viewer is pointing at, drawn over the activity map. */
  highlight: [overlays: MapOverlay[]]
}>()

const { t } = useI18n()
const toasts = useToasts()
const { enabled } = useSegmentsSettings()

const sportGroup = computed(() => sportGroupOf(props.activity.activityType))
const { data: efforts } = useActivitySegmentEffortsQuery(
  () => props.activity.id,
  () => enabled.value && sportGroup.value !== null,
)
const excludeMutation = useSetEffortExcludedMutation()
const isCreateOpen = ref(false)

const canCreate = computed(
  () =>
    props.isOwner &&
    enabled.value &&
    sportGroup.value !== null &&
    props.track.length >= MIN_SEGMENT_POINTS,
)
const rows = computed(() => efforts.value ?? [])
// Other viewers only see the card when there is something in it; the owner
// also gets it as the place to create segments.
const isVisible = computed(
  () => enabled.value && sportGroup.value !== null && (rows.value.length > 0 || canCreate.value),
)

/** Effort row text: time, then pace or speed when the owner shares it. */
function summary(effort: SegmentEffort): string {
  const parts = [formatHmsDuration(effort.elapsedTime)]
  if (sportGroup.value && effort.averageSpeed !== null) {
    parts.push(formatEffortSpeed(effort.averageSpeed, sportGroup.value, props.units))
  }
  if (effort.averageHr !== null) {
    parts.push(`${effort.averageHr} bpm`)
  }
  return parts.join(' · ')
}

/** "+0:12 vs PR" for efforts slower than the owner's PR. */
function prDelta(effort: SegmentEffort): string | null {
  if (effort.prElapsedTime === null || effort.currentRank === 1 || effort.isExcluded) {
    return null
  }
  return t('segments.efforts.vsPr', {
    delta: formatTimeDelta(effort.elapsedTime, effort.prElapsedTime),
  })
}

function highlight(effort: SegmentEffort | null): void {
  if (!effort) {
    emit('highlight', [])
    return
  }
  emit('highlight', [
    {
      id: `effort-${effort.id}`,
      points: sliceTrack(props.track, effort.startIndex, effort.endIndex),
      style: 'highlight',
    },
  ])
}

function toggleExcluded(effort: SegmentEffort): void {
  excludeMutation.mutate(
    { id: effort.id, isExcluded: !effort.isExcluded },
    {
      onSuccess: () => {
        toasts.success(
          effort.isExcluded ? t('segments.efforts.restored') : t('segments.efforts.excluded'),
        )
      },
      onError: () => toasts.error(t('segments.efforts.excludeError')),
    },
  )
}
</script>

<template>
  <Card v-if="isVisible" padding="none" class="flex flex-col">
    <div class="flex items-center justify-between gap-3 px-4 py-3">
      <h2 class="text-card-heading">{{ t('segments.efforts.title') }}</h2>
      <Button v-if="canCreate" variant="outline" size="sm" @click="isCreateOpen = true">
        <Plus class="size-4" aria-hidden="true" />
        {{ t('segments.efforts.create') }}
      </Button>
    </div>

    <p v-if="rows.length === 0" class="border-t border-border px-4 py-3 text-hint">
      {{ t('segments.efforts.empty') }}
    </p>
    <ul v-else class="divide-y divide-border border-t border-border" @mouseleave="highlight(null)">
      <li
        v-for="effort in rows"
        :key="effort.id"
        class="flex items-center gap-3 px-4 py-3"
        :class="{ 'opacity-60': effort.isExcluded }"
        @mouseenter="highlight(effort)"
        @focusin="highlight(effort)"
      >
        <SegmentMedal v-if="!effort.isExcluded" :rank="effort.historicalRank" />
        <Flag
          v-if="effort.isExcluded || effort.historicalRank === null || effort.historicalRank > 3"
          class="size-5 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <div class="min-w-0 flex-1">
          <RouterLink
            :to="{ name: 'segment', params: { id: effort.segmentId } }"
            class="block truncate font-medium text-foreground hover:underline"
          >
            {{ effort.segmentName ?? t('segments.efforts.unnamed') }}
          </RouterLink>
          <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-hint tabular-nums">
            <span>{{ summary(effort) }}</span>
            <span v-if="effort.isExcluded">{{ t('segments.efforts.excludedLabel') }}</span>
            <template v-else-if="effort.currentRank !== null">
              <span>{{ t('segments.efforts.currentRank', { rank: effort.currentRank }) }}</span>
              <span v-if="prDelta(effort)">{{ prDelta(effort) }}</span>
            </template>
          </div>
        </div>
        <Button
          v-if="isOwner"
          variant="ghost"
          size="icon"
          :aria-label="
            effort.isExcluded ? t('segments.efforts.restore') : t('segments.efforts.exclude')
          "
          :title="effort.isExcluded ? t('segments.efforts.restore') : t('segments.efforts.exclude')"
          :disabled="excludeMutation.isPending.value"
          @click="toggleExcluded(effort)"
        >
          <Eye v-if="effort.isExcluded" class="size-4" aria-hidden="true" />
          <EyeOff v-else class="size-4" aria-hidden="true" />
        </Button>
      </li>
    </ul>

    <SegmentCreateDialog
      v-if="canCreate && sportGroup"
      v-model:open="isCreateOpen"
      :activity-id="activity.id"
      :activity-type="activity.activityType"
      :sport-group="sportGroup"
      :track="track"
      :units="units"
      @success="toasts.success"
      @error="toasts.error"
    />
  </Card>
</template>
