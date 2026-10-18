<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Lock, Pencil, RefreshCw, Trash2 } from '@lucide/vue'

import type { GeoPoint } from '@/composables/useMapProvider'

import ActivityMap from '@/features/activities/components/ActivityMap.vue'
import ActivityStreamChart from '@/features/activities/components/ActivityStreamChart.vue'
import SegmentEditDialog from '@/features/segments/components/SegmentEditDialog.vue'
import SegmentLeaderboard from '@/features/segments/components/SegmentLeaderboard.vue'
import SegmentMyEfforts from '@/features/segments/components/SegmentMyEfforts.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorState } from '@/components/ui/error-state'
import { MetricPill } from '@/components/ui/metric-pill'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useCurrentUser } from '@/features/auth/composables/useCurrentUser'
import { useToasts } from '@/composables/useToasts'
import { formatDistance, formatElevation } from '@/features/activities/utils/format'
import { buildElevationProfile } from '@/features/routes/utils/elevationProfile'
import {
  useDeleteSegmentMutation,
  useRematchSegmentMutation,
  useSegmentQuery,
} from '@/features/segments/composables/useSegments'
import { SEGMENT_VISIBILITY } from '@/features/segments/types'

const currentRoute = useRoute()
const router = useRouter()
const { t } = useI18n()
const toasts = useToasts()
const { data: currentUser } = useCurrentUser()
const units = computed(() => currentUser.value?.units ?? 'metric')
const viewerId = computed(() => currentUser.value?.id ?? null)

const segmentId = computed(() => {
  const raw = Number(currentRoute.params.id)
  return Number.isFinite(raw) && raw > 0 ? raw : null
})
const { data: segment, isPending, isError, error, refetch } = useSegmentQuery(segmentId)
const isNotFound = computed(
  () => isError.value && (error.value as { status?: number } | null)?.status === 404,
)
const isOwner = computed(
  () => !!segment.value && viewerId.value !== null && segment.value.userId === viewerId.value,
)

const mapPoints = computed<GeoPoint[]>(
  () => segment.value?.points.map((point) => ({ lat: point.lat, lng: point.lng })) ?? [],
)
const profile = computed(() =>
  segment.value
    ? buildElevationProfile(segment.value.points, units.value, t('segments.detail.elevation'))
    : null,
)
const place = computed(() =>
  [segment.value?.city, segment.value?.country].filter(Boolean).join(', '),
)

function formatGrade(grade: number | null): { value: string; unit: string } {
  return { value: grade === null ? '--' : grade.toFixed(1), unit: '%' }
}

const stats = computed(() => {
  const value = segment.value
  if (!value) {
    return []
  }
  return [
    {
      key: 'distance',
      label: t('segments.stats.distance'),
      metric: formatDistance(value.distance, 1, units.value),
    },
    {
      key: 'averageGrade',
      label: t('segments.stats.averageGrade'),
      metric: formatGrade(value.averageGrade),
    },
    {
      key: 'maximumGrade',
      label: t('segments.stats.maximumGrade'),
      metric: formatGrade(value.maximumGrade),
    },
    {
      key: 'gain',
      label: t('segments.stats.elevationGain'),
      metric: formatElevation(value.elevationGain, units.value),
    },
    {
      key: 'efforts',
      label: t('segments.stats.efforts'),
      metric: { value: String(value.effortCount), unit: '' },
    },
    {
      key: 'athletes',
      label: t('segments.stats.athletes'),
      metric: { value: String(value.athleteCount), unit: '' },
    },
  ]
})

const tab = ref('leaderboard')
const isEditOpen = ref(false)
const isDeleteOpen = ref(false)
const deleteMutation = useDeleteSegmentMutation()
const rematchMutation = useRematchSegmentMutation()

function confirmDelete(): void {
  const value = segment.value
  if (!value) {
    return
  }
  deleteMutation.mutate(value.id, {
    onSuccess: () => {
      isDeleteOpen.value = false
      toasts.success(t('segments.delete.success'))
      void router.push(
        value.sourceActivityId
          ? { name: 'activity', params: { id: value.sourceActivityId } }
          : { name: 'home' },
      )
    },
    onError: () => toasts.error(t('segments.delete.error')),
  })
}

function rematch(): void {
  const value = segment.value
  if (!value) {
    return
  }
  rematchMutation.mutate(value.id, {
    onSuccess: () => toasts.success(t('segments.actions.rematchQueued')),
    onError: () => toasts.error(t('segments.actions.rematchError')),
  })
}
</script>

<template>
  <section class="flex flex-col gap-3">
    <Button variant="ghost" size="sm" class="self-start" @click="router.back()">
      <ArrowLeft class="size-4" aria-hidden="true" />
      {{ t('segments.detail.back') }}
    </Button>

    <template v-if="isPending">
      <header class="flex flex-col gap-1" aria-busy="true">
        <Skeleton class="h-7 w-56" />
        <Skeleton class="h-4 w-32" />
      </header>
      <Skeleton class="h-80 w-full rounded-card" />
      <Skeleton class="h-48 w-full rounded-card" />
    </template>

    <EmptyState
      v-else-if="isNotFound || (!isError && !segment)"
      :title="t('segments.detail.notFoundTitle')"
      :description="t('segments.detail.notFoundDescription')"
    />

    <ErrorState
      v-else-if="isError || !segment"
      :title="t('segments.error.title')"
      :description="t('segments.error.description')"
      @retry="() => refetch()"
    >
      <template #action="{ retry }">
        <Button variant="outline" @click="retry">{{ t('segments.error.retry') }}</Button>
      </template>
    </ErrorState>

    <template v-else>
      <header class="flex flex-wrap items-start justify-between gap-3">
        <div class="flex min-w-0 flex-col gap-1">
          <h1 class="text-page-title break-words">{{ segment.name }}</h1>
          <p class="flex flex-wrap items-center gap-2 text-body">
            <Badge variant="secondary">{{ t(`segments.sportGroup.${segment.sportGroup}`) }}</Badge>
            <Badge v-if="segment.visibility === SEGMENT_VISIBILITY.private" variant="outline">
              <Lock class="mr-1 size-3" aria-hidden="true" />
              {{ t('segments.visibility.private') }}
            </Badge>
            <span v-if="place">{{ place }}</span>
            <RouterLink
              v-if="isOwner && segment.sourceActivityId"
              :to="{ name: 'activity', params: { id: segment.sourceActivityId } }"
              class="underline"
            >
              {{ t('segments.detail.sourceActivity') }}
            </RouterLink>
          </p>
        </div>
        <div v-if="isOwner" class="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" @click="isEditOpen = true">
            <Pencil class="size-4" aria-hidden="true" />
            {{ t('segments.actions.edit') }}
          </Button>
          <Button
            variant="outline"
            size="sm"
            :disabled="rematchMutation.isPending.value"
            @click="rematch"
          >
            <RefreshCw class="size-4" aria-hidden="true" />
            {{ t('segments.actions.rematch') }}
          </Button>
          <Button variant="ghostDestructive" size="sm" @click="isDeleteOpen = true">
            <Trash2 class="size-4" aria-hidden="true" />
            {{ t('segments.actions.delete') }}
          </Button>
        </div>
      </header>

      <Card class="flex flex-col gap-4">
        <div class="flex flex-wrap gap-4">
          <MetricPill
            v-for="stat in stats"
            :key="stat.key"
            :label="stat.label"
            :value="stat.metric.value"
            :unit="stat.metric.unit"
          />
        </div>
        <p v-if="segment.description" class="text-body whitespace-pre-line">
          {{ segment.description }}
        </p>
      </Card>

      <Card padding="none" class="h-72 overflow-hidden lg:h-96">
        <ActivityMap :points="mapPoints" />
      </Card>

      <ActivityStreamChart
        v-if="profile"
        :title="t('segments.detail.elevation')"
        :render="profile"
      />

      <Card class="flex flex-col gap-3">
        <Tabs v-model="tab">
          <TabsList>
            <TabsTrigger value="leaderboard">{{ t('segments.detail.leaderboardTab') }}</TabsTrigger>
            <TabsTrigger value="mine">{{ t('segments.detail.myEffortsTab') }}</TabsTrigger>
          </TabsList>
          <TabsContent value="leaderboard">
            <SegmentLeaderboard
              :segment-id="segment.id"
              :sport-group="segment.sportGroup"
              :units="units"
              :viewer-id="viewerId"
            />
          </TabsContent>
          <TabsContent value="mine">
            <SegmentMyEfforts
              :segment-id="segment.id"
              :sport-group="segment.sportGroup"
              :units="units"
            />
          </TabsContent>
        </Tabs>
      </Card>

      <SegmentEditDialog
        v-if="isOwner"
        v-model:open="isEditOpen"
        :segment="segment"
        @success="toasts.success"
        @error="toasts.error"
      />
      <ConfirmDialog
        v-model:open="isDeleteOpen"
        :title="t('segments.delete.title')"
        :description="t('segments.delete.body', { name: segment.name })"
        :confirm-label="t('segments.delete.confirm')"
        :cancel-label="t('segments.delete.cancel')"
        :close-label="t('segments.delete.close')"
        :pending="deleteMutation.isPending.value"
        @confirm="confirmDelete"
      />
    </template>
  </section>
</template>
