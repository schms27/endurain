<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Repeat, Route as RouteIcon } from '@lucide/vue'

import type { Units } from '@/features/activities/utils/format'
import type { RouteSummary } from '@/features/routes/types'

import { Badge } from '@/components/ui/badge'
import { combineMetric, formatDistance, formatElevation } from '@/features/activities/utils/format'
import { ROUTE_SOURCE } from '@/features/routes/types'

const props = defineProps<{ route: RouteSummary; units: Units }>()

const { t } = useI18n()

// Routes are never swims, so any non-swim type gives km/mi.
const distance = computed(() =>
  combineMetric(formatDistance(props.route.distance, props.route.activityType ?? 1, props.units)),
)
const gain = computed(() =>
  props.route.elevationGain !== null
    ? `↑ ${combineMetric(formatElevation(props.route.elevationGain, props.units))}`
    : null,
)
const place = computed(() => [props.route.city, props.route.country].filter(Boolean).join(', '))
const sourceLabel = computed(() =>
  props.route.source === ROUTE_SOURCE.activity
    ? t('routes.item.fromActivity')
    : t('routes.item.imported'),
)
</script>

<template>
  <div class="flex items-center gap-3 px-4 py-3">
    <span
      class="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground"
    >
      <RouteIcon class="size-5" aria-hidden="true" />
    </span>
    <div class="min-w-0 flex-1">
      <RouterLink
        :to="{ name: 'route', params: { id: route.id } }"
        class="block truncate font-medium text-foreground hover:underline"
      >
        {{ route.name }}
      </RouterLink>
      <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-hint">
        <span>{{ distance }}</span>
        <span v-if="gain">{{ gain }}</span>
        <span v-if="place" class="truncate">{{ place }}</span>
      </div>
    </div>
    <div class="flex shrink-0 items-center gap-1">
      <Badge v-if="route.isLoop" variant="secondary">
        <Repeat class="size-3" aria-hidden="true" />
        {{ t('routes.item.loop') }}
      </Badge>
      <Badge variant="outline" class="hidden sm:inline-flex">{{ sourceLabel }}</Badge>
    </div>
  </div>
</template>
