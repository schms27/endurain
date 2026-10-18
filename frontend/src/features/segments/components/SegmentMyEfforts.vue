<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import type { Units } from '@/features/activities/utils/format'
import type { SportGroup } from '@/features/segments/types'

import ActivityStreamChart from '@/features/activities/components/ActivityStreamChart.vue'
import SegmentMedal from '@/features/segments/components/SegmentMedal.vue'
import { Skeleton } from '@/components/ui/skeleton'
import { formatHmsDuration } from '@/features/activities/utils/format'
import { useMySegmentEffortsQuery } from '@/features/segments/composables/useSegments'
import {
  buildEffortHistoryChart,
  formatEffortSpeed,
  formatTimeDelta,
} from '@/features/segments/utils/segments'
import { formatMediumDate } from '@/utils/datetime'

const props = defineProps<{
  segmentId: number
  sportGroup: SportGroup
  units: Units
}>()

const { t, locale } = useI18n()

const { data, isPending } = useMySegmentEffortsQuery(() => props.segmentId)
// The API returns the fastest first; the list reads newest first.
const efforts = computed(() =>
  [...(data.value ?? [])].sort((a, b) => b.startTime.localeCompare(a.startTime)),
)
const personalRecord = computed(
  () => efforts.value.find((effort) => !effort.isExcluded && effort.currentRank === 1) ?? null,
)
const history = computed(() =>
  buildEffortHistoryChart(efforts.value, t('segments.myEfforts.chartLabel'), (iso) =>
    formatMediumDate(iso, locale.value),
  ),
)
</script>

<template>
  <div class="flex flex-col gap-3">
    <div v-if="isPending" class="flex flex-col gap-2" aria-busy="true">
      <Skeleton v-for="n in 3" :key="n" class="h-10 w-full" />
    </div>

    <p v-else-if="efforts.length === 0" class="text-hint">{{ t('segments.myEfforts.empty') }}</p>

    <template v-else>
      <p v-if="personalRecord" class="text-body">
        {{ t('segments.myEfforts.pr', { time: formatHmsDuration(personalRecord.elapsedTime) }) }}
      </p>
      <ActivityStreamChart
        v-if="history"
        :title="t('segments.myEfforts.chartTitle')"
        :render="history"
      />
      <ul class="divide-y divide-border">
        <li
          v-for="effort in efforts"
          :key="effort.id"
          class="flex items-center gap-3 py-2"
          :class="{ 'opacity-60': effort.isExcluded }"
        >
          <SegmentMedal :rank="effort.isExcluded ? null : effort.historicalRank" />
          <div class="min-w-0 flex-1">
            <RouterLink
              :to="{ name: 'activity', params: { id: effort.activityId } }"
              class="font-medium text-foreground hover:underline"
            >
              {{ formatMediumDate(effort.startTime, locale) }}
            </RouterLink>
            <p class="text-hint tabular-nums">
              {{ formatEffortSpeed(effort.averageSpeed, sportGroup, units) }}
              <template v-if="effort.isExcluded">
                · {{ t('segments.efforts.excludedLabel') }}</template
              >
              <template
                v-else-if="
                  personalRecord && effort.id !== personalRecord.id && effort.prElapsedTime !== null
                "
              >
                ·
                {{
                  t('segments.efforts.vsPr', {
                    delta: formatTimeDelta(effort.elapsedTime, effort.prElapsedTime),
                  })
                }}
              </template>
            </p>
          </div>
          <span class="tabular-nums font-medium">{{ formatHmsDuration(effort.elapsedTime) }}</span>
        </li>
      </ul>
    </template>
  </div>
</template>
