<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Download, MapPin, Pencil, Trash2 } from '@lucide/vue'

import type { GeoPoint } from '@/composables/useMapProvider'
import type { RoutePoi } from '@/features/routes/types'

import ActivityMap from '@/features/activities/components/ActivityMap.vue'
import ActivityStreamChart from '@/features/activities/components/ActivityStreamChart.vue'
import RouteEditDialog from '@/features/routes/components/RouteEditDialog.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorState } from '@/components/ui/error-state'
import { MetricPill } from '@/components/ui/metric-pill'
import { Skeleton } from '@/components/ui/skeleton'
import { useCurrentUser } from '@/features/auth/composables/useCurrentUser'
import { useToasts } from '@/composables/useToasts'
import { downloadBlob } from '@/lib/download'
import { formatDistance, formatElevation } from '@/features/activities/utils/format'
import { useDeleteRouteMutation, useRouteQuery } from '@/features/routes/composables/useRoutes'
import { exportRouteGpx } from '@/features/routes/services/routes'
import { ROUTE_SOURCE } from '@/features/routes/types'
import { buildElevationProfile } from '@/features/routes/utils/elevationProfile'

const POI_KIND_KEYS = {
  generic: 'routes.poi.generic',
  water: 'routes.poi.water',
  food: 'routes.poi.food',
  summit: 'routes.poi.summit',
  viewpoint: 'routes.poi.viewpoint',
  danger: 'routes.poi.danger',
  shelter: 'routes.poi.shelter',
  toilet: 'routes.poi.toilet',
} as const satisfies Record<RoutePoi['kind'], string>

const currentRoute = useRoute()
const router = useRouter()
const { t } = useI18n()
const toasts = useToasts()
const { data: currentUser } = useCurrentUser()
const units = computed(() => currentUser.value?.units ?? 'metric')

const routeId = computed(() => {
  const raw = Number(currentRoute.params.id)
  return Number.isFinite(raw) && raw > 0 ? raw : null
})
const { data: plannedRoute, isPending, isError, error, refetch } = useRouteQuery(routeId)
const isNotFound = computed(
  () => isError.value && (error.value as { status?: number } | null)?.status === 404,
)

const mapPoints = computed<GeoPoint[]>(
  () => plannedRoute.value?.points.map((point) => ({ lat: point.lat, lng: point.lng })) ?? [],
)
const profile = computed(() =>
  plannedRoute.value
    ? buildElevationProfile(plannedRoute.value.points, units.value, t('routes.detail.elevation'))
    : null,
)
const stats = computed(() => {
  const value = plannedRoute.value
  if (!value) {
    return []
  }
  const type = value.activityType ?? 1
  const rows = [
    {
      key: 'distance',
      label: t('routes.stats.distance'),
      metric: formatDistance(value.distance, type, units.value),
    },
    {
      key: 'gain',
      label: t('routes.stats.elevationGain'),
      metric: formatElevation(value.elevationGain, units.value),
    },
    {
      key: 'loss',
      label: t('routes.stats.elevationLoss'),
      metric: formatElevation(value.elevationLoss, units.value),
    },
  ]
  if (value.elevationMax !== null) {
    rows.push({
      key: 'max',
      label: t('routes.stats.highest'),
      metric: formatElevation(value.elevationMax, units.value),
    })
  }
  return rows
})

const isExporting = ref(false)
async function downloadGpx(): Promise<void> {
  const value = plannedRoute.value
  if (!value) {
    return
  }
  isExporting.value = true
  try {
    const blob = await exportRouteGpx(value.id)
    const slug = value.name
      .replace(/[^a-z0-9]+/gi, '-')
      .replace(/^-|-$/g, '')
      .toLowerCase()
    downloadBlob(blob, `${slug || 'route'}.gpx`)
  } catch {
    toasts.error(t('routes.actions.exportError'))
  } finally {
    isExporting.value = false
  }
}

const isEditOpen = ref(false)
const isDeleteOpen = ref(false)
const deleteMutation = useDeleteRouteMutation()

function confirmDelete(): void {
  const value = plannedRoute.value
  if (!value) {
    return
  }
  deleteMutation.mutate(value.id, {
    onSuccess: () => {
      isDeleteOpen.value = false
      toasts.success(t('routes.delete.success'))
      void router.push({ name: 'routes' })
    },
    onError: () => {
      toasts.error(t('routes.delete.error'))
    },
  })
}
</script>

<template>
  <section class="flex flex-col gap-3">
    <Button variant="ghost" size="sm" class="self-start" @click="router.push({ name: 'routes' })">
      <ArrowLeft class="size-4" aria-hidden="true" />
      {{ t('routes.detail.back') }}
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
      v-else-if="isNotFound || (!isError && !plannedRoute)"
      :title="t('routes.detail.notFoundTitle')"
      :description="t('routes.detail.notFoundDescription')"
    >
      <template #action>
        <Button variant="outline" @click="router.push({ name: 'routes' })">
          {{ t('routes.detail.back') }}
        </Button>
      </template>
    </EmptyState>

    <ErrorState
      v-else-if="isError || !plannedRoute"
      :title="t('routes.error.title')"
      :description="t('routes.error.description')"
      @retry="() => refetch()"
    >
      <template #action="{ retry }">
        <Button variant="outline" @click="retry">{{ t('routes.error.retry') }}</Button>
      </template>
    </ErrorState>

    <template v-else>
      <header class="flex flex-wrap items-start justify-between gap-3">
        <div class="flex min-w-0 flex-col gap-1">
          <h1 class="text-page-title break-words">{{ plannedRoute.name }}</h1>
          <p
            v-if="plannedRoute.source === ROUTE_SOURCE.activity && plannedRoute.sourceActivityId"
            class="text-body"
          >
            {{ t('routes.detail.sourceActivity') }} ·
            <RouterLink
              :to="{ name: 'activity', params: { id: plannedRoute.sourceActivityId } }"
              class="underline"
            >
              {{ t('routes.detail.viewActivity') }}
            </RouterLink>
          </p>
          <p v-else-if="plannedRoute.originalFilename" class="text-body">
            {{ t('routes.detail.importedFrom', { filename: plannedRoute.originalFilename }) }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" :disabled="isExporting" @click="downloadGpx">
            <Download class="size-4" aria-hidden="true" />
            {{ t('routes.actions.export') }}
          </Button>
          <Button variant="outline" size="sm" @click="isEditOpen = true">
            <Pencil class="size-4" aria-hidden="true" />
            {{ t('routes.actions.edit') }}
          </Button>
          <Button variant="ghostDestructive" size="sm" @click="isDeleteOpen = true">
            <Trash2 class="size-4" aria-hidden="true" />
            {{ t('routes.actions.delete') }}
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
        <p v-if="plannedRoute.description" class="text-body whitespace-pre-line">
          {{ plannedRoute.description }}
        </p>
      </Card>

      <Card padding="none" class="h-80 overflow-hidden lg:h-[28rem]">
        <ActivityMap :points="mapPoints" />
      </Card>

      <ActivityStreamChart v-if="profile" :title="t('routes.detail.elevation')" :render="profile" />
      <Card v-else>
        <p class="text-hint">{{ t('routes.detail.noElevation') }}</p>
      </Card>

      <Card v-if="plannedRoute.pois.length > 0" padding="none" class="divide-y divide-border">
        <h2 class="px-4 py-3 text-card-heading">{{ t('routes.detail.pointsOfInterest') }}</h2>
        <ul class="divide-y divide-border">
          <li
            v-for="(poi, index) in plannedRoute.pois"
            :key="`${index}-${poi.lat}-${poi.lng}`"
            class="flex items-start gap-3 px-4 py-3"
          >
            <MapPin class="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div class="min-w-0">
              <p class="font-medium text-foreground">{{ poi.name }}</p>
              <p class="text-hint">
                {{ t(POI_KIND_KEYS[poi.kind]) }}
                <template v-if="poi.description"> · {{ poi.description }}</template>
              </p>
            </div>
          </li>
        </ul>
      </Card>

      <RouteEditDialog
        v-model:open="isEditOpen"
        :route="plannedRoute"
        @success="toasts.success"
        @error="toasts.error"
      />
      <ConfirmDialog
        v-model:open="isDeleteOpen"
        :title="t('routes.delete.title')"
        :description="t('routes.delete.body', { name: plannedRoute.name })"
        :confirm-label="t('routes.delete.confirm')"
        :cancel-label="t('routes.delete.cancel')"
        :close-label="t('routes.delete.close')"
        :pending="deleteMutation.isPending.value"
        @confirm="confirmDelete"
      />
    </template>
  </section>
</template>
