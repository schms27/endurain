<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import type { Units } from '@/features/activities/utils/format'
import type {
  LeaderboardEntry,
  LeaderboardPeriod,
  LeaderboardScope,
  SportGroup,
} from '@/features/segments/types'

import UserAvatar from '@/components/UserAvatar.vue'
import { Button } from '@/components/ui/button'
import { ErrorState } from '@/components/ui/error-state'
import { FormField } from '@/components/ui/form-field'
import { Pagination } from '@/components/ui/pagination'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useListPagination } from '@/composables/useListPagination'
import { formatHmsDuration } from '@/features/activities/utils/format'
import { resolveAvatarUrl } from '@/features/auth/services/mappers'
import { useSegmentLeaderboardQuery } from '@/features/segments/composables/useSegments'
import { formatEffortSpeed } from '@/features/segments/utils/segments'
import { formatMediumDate } from '@/utils/datetime'

const props = defineProps<{
  segmentId: number
  sportGroup: SportGroup
  units: Units
  viewerId: number | null
}>()

const { t, locale } = useI18n()

/** Rows per leaderboard page. */
const PAGE_SIZE = 25

const SCOPES: { value: LeaderboardScope; labelKey: string }[] = [
  { value: 'everyone', labelKey: 'segments.leaderboard.scopeEveryone' },
  { value: 'following', labelKey: 'segments.leaderboard.scopeFollowing' },
  { value: 'me', labelKey: 'segments.leaderboard.scopeMe' },
]
const PERIODS: { value: LeaderboardPeriod; labelKey: string }[] = [
  { value: 'all', labelKey: 'segments.leaderboard.periodAll' },
  { value: 'this_year', labelKey: 'segments.leaderboard.periodThisYear' },
  { value: 'last_90_days', labelKey: 'segments.leaderboard.periodLast90Days' },
]

const scope = ref<LeaderboardScope>('everyone')
const period = ref<LeaderboardPeriod>('all')
const page = ref(1)

const query = useSegmentLeaderboardQuery(() => props.segmentId, scope, period, page, PAGE_SIZE)
const entries = computed(() => query.data.value?.entries ?? [])
const total = computed(() => query.data.value?.total ?? 0)
const viewerEntry = computed(() => query.data.value?.viewerEntry ?? null)
const { totalPages, reset } = useListPagination(page, total, PAGE_SIZE)
watch([scope, period], reset)

// Show the viewer's own row under the table when it is not on this page.
const viewerOffPage = computed(
  () =>
    viewerEntry.value !== null &&
    !entries.value.some((entry) => entry.userId === viewerEntry.value?.userId),
)

function isViewer(entry: LeaderboardEntry): boolean {
  return entry.userId === props.viewerId
}

function displayName(entry: LeaderboardEntry): string {
  return entry.userName ?? entry.username ?? t('segments.leaderboard.unknownAthlete')
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <FormField :label="t('segments.leaderboard.scope')">
        <template #default="{ fieldId }">
          <Select :id="fieldId" v-model="scope">
            <option v-for="option in SCOPES" :key="option.value" :value="option.value">
              {{ t(option.labelKey) }}
            </option>
          </Select>
        </template>
      </FormField>
      <FormField :label="t('segments.leaderboard.period')">
        <template #default="{ fieldId }">
          <Select :id="fieldId" v-model="period">
            <option v-for="option in PERIODS" :key="option.value" :value="option.value">
              {{ t(option.labelKey) }}
            </option>
          </Select>
        </template>
      </FormField>
    </div>

    <div v-if="query.isPending.value" class="flex flex-col gap-2" aria-busy="true">
      <Skeleton v-for="n in 5" :key="n" class="h-10 w-full" />
    </div>

    <ErrorState
      v-else-if="query.isError.value"
      :title="t('segments.leaderboard.errorTitle')"
      :description="t('segments.leaderboard.errorDescription')"
      @retry="() => query.refetch()"
    >
      <template #action="{ retry }">
        <Button variant="outline" size="sm" @click="retry">{{ t('segments.error.retry') }}</Button>
      </template>
    </ErrorState>

    <p v-else-if="entries.length === 0" class="text-hint">{{ t('segments.leaderboard.empty') }}</p>

    <template v-else>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-caption">
              <th scope="col" class="py-2 pr-3">{{ t('segments.leaderboard.rank') }}</th>
              <th scope="col" class="py-2 pr-3">{{ t('segments.leaderboard.athlete') }}</th>
              <th scope="col" class="hidden py-2 pr-3 sm:table-cell">
                {{ t('segments.leaderboard.date') }}
              </th>
              <th scope="col" class="py-2 pr-3 text-right">{{ t('segments.leaderboard.time') }}</th>
              <th scope="col" class="hidden py-2 text-right sm:table-cell">
                {{ t('segments.leaderboard.speed') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr
              v-for="entry in viewerOffPage && viewerEntry ? [...entries, viewerEntry] : entries"
              :key="`${entry.userId}-${entry.effortId}`"
              :class="{ 'bg-muted/60 font-medium': isViewer(entry) }"
            >
              <td class="py-2 pr-3 tabular-nums">{{ entry.rank }}</td>
              <td class="py-2 pr-3">
                <span class="flex min-w-0 items-center gap-2">
                  <UserAvatar
                    :src="resolveAvatarUrl(entry.userPhotoPath)"
                    :alt="displayName(entry)"
                    size-class="size-7"
                  />
                  <RouterLink
                    v-if="entry.username"
                    :to="{ name: 'user', params: { id: entry.userId } }"
                    class="truncate hover:underline"
                  >
                    {{ displayName(entry) }}
                  </RouterLink>
                  <span v-else class="truncate">{{ displayName(entry) }}</span>
                </span>
              </td>
              <td class="hidden py-2 pr-3 sm:table-cell">
                <RouterLink
                  :to="{ name: 'activity', params: { id: entry.activityId } }"
                  class="hover:underline"
                >
                  {{
                    entry.startTime
                      ? formatMediumDate(entry.startTime, locale)
                      : t('segments.leaderboard.viewActivity')
                  }}
                </RouterLink>
              </td>
              <td class="py-2 pr-3 text-right tabular-nums">
                {{ formatHmsDuration(entry.elapsedTime) }}
              </td>
              <td class="hidden py-2 text-right tabular-nums sm:table-cell">
                {{ formatEffortSpeed(entry.averageSpeed, sportGroup, units) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-hint">{{ t('segments.leaderboard.total', { count: total }, total) }}</p>
      <Pagination v-if="totalPages > 1" v-model:page="page" :total-pages="totalPages" />
    </template>
  </div>
</template>
