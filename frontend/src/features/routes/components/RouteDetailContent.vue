<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MapPin } from '@lucide/vue'

import type { GeoPoint } from '@/composables/useMapProvider'
import type { Units } from '@/features/activities/utils/format'
import type { RouteDetail, RoutePoi } from '@/features/routes/types'

import ActivityMap from '@/features/activities/components/ActivityMap.vue'
import ActivityStreamChart from '@/features/activities/components/ActivityStreamChart.vue'
import { Card } from '@/components/ui/card'
import { MetricPill } from '@/components/ui/metric-pill'
import { formatDistance, formatElevation } from '@/features/activities/utils/format'
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

const props = defineProps<{ route: RouteDetail; units: Units }>()

const { t } = useI18n()

const mapPoints = computed<GeoPoint[]>(() =>
  props.route.points.map((point) => ({ lat: point.lat, lng: point.lng })),
)
const profile = computed(() =>
  buildElevationProfile(props.route.points, props.units, t('routes.detail.elevation')),
)
const stats = computed(() => {
  const value = props.route
  const type = value.activityType ?? 1
  const rows = [
    {
      key: 'distance',
      label: t('routes.stats.distance'),
      metric: formatDistance(value.distance, type, props.units),
    },
    {
      key: 'gain',
      label: t('routes.stats.elevationGain'),
      metric: formatElevation(value.elevationGain, props.units),
    },
    {
      key: 'loss',
      label: t('routes.stats.elevationLoss'),
      metric: formatElevation(value.elevationLoss, props.units),
    },
  ]
  if (value.elevationMax !== null) {
    rows.push({
      key: 'max',
      label: t('routes.stats.highest'),
      metric: formatElevation(value.elevationMax, props.units),
    })
  }
  return rows
})
</script>

<template>
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
    <p v-if="route.description" class="text-body whitespace-pre-line">
      {{ route.description }}
    </p>
  </Card>

  <Card padding="none" class="h-80 overflow-hidden lg:h-[28rem]">
    <ActivityMap :points="mapPoints" />
  </Card>

  <ActivityStreamChart v-if="profile" :title="t('routes.detail.elevation')" :render="profile" />
  <Card v-else>
    <p class="text-hint">{{ t('routes.detail.noElevation') }}</p>
  </Card>

  <Card v-if="route.pois.length > 0" padding="none" class="divide-y divide-border">
    <h2 class="px-4 py-3 text-card-heading">{{ t('routes.detail.pointsOfInterest') }}</h2>
    <ul class="divide-y divide-border">
      <li
        v-for="(poi, index) in route.pois"
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
</template>
