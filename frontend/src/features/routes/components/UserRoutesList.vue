<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Route as RouteIcon } from '@lucide/vue'

import type { Units } from '@/features/activities/utils/format'

import RouteListItem from '@/features/routes/components/RouteListItem.vue'
import { EmptyState } from '@/components/ui/empty-state'
import { ListPanel } from '@/components/ui/list-panel'
import { Skeleton } from '@/components/ui/skeleton'
import { useRecordsPerPage } from '@/features/config/composables/useRecordsPerPage'
import { useListPagination } from '@/composables/useListPagination'
import { useUserRoutesQuery } from '@/features/routes/composables/useRoutes'

/** The routes on a user's profile that the viewer can see. */
const props = defineProps<{
  userId: number | null
  isSelf: boolean
  units: Units
  /** Only fetch while the profile tab is open. */
  active: boolean
}>()

const { t } = useI18n()

const page = ref(1)
const { recordsPerPage } = useRecordsPerPage()
const query = useUserRoutesQuery(
  () => props.userId,
  page,
  recordsPerPage,
  () => props.active,
)
const routes = computed(() => query.data.value?.records ?? [])
const totalCount = computed(() => query.data.value?.total ?? 0)
const { totalPages, reset: resetPage } = useListPagination(page, totalCount, recordsPerPage)
watch(() => props.userId, resetPage)

const isEmpty = computed(
  () => !query.isPending.value && !query.isError.value && routes.value.length === 0,
)
</script>

<template>
  <ListPanel
    v-model:page="page"
    :is-loading="query.isPending.value"
    :is-error="query.isError.value"
    :is-empty="isEmpty"
    :show-header="false"
    :error-title="t('routes.error.title')"
    :error-description="t('routes.error.description')"
    :retry-label="t('routes.error.retry')"
    :paginated="true"
    :total-pages="totalPages"
    @retry="() => query.refetch()"
  >
    <template #loading>
      <div class="divide-y divide-border" aria-busy="true">
        <div v-for="n in 3" :key="n" class="flex items-center gap-3 px-4 py-3">
          <Skeleton class="size-10 shrink-0 rounded-full" />
          <div class="flex-1 space-y-2">
            <Skeleton class="h-4 w-1/3" />
            <Skeleton class="h-3 w-1/4" />
          </div>
        </div>
      </div>
    </template>

    <template #empty>
      <EmptyState
        :title="isSelf ? t('routes.profile.ownEmptyTitle') : t('routes.profile.otherEmptyTitle')"
        :description="isSelf ? t('routes.profile.ownEmptyDescription') : undefined"
      >
        <template #icon>
          <RouteIcon class="size-8" aria-hidden="true" />
        </template>
      </EmptyState>
    </template>

    <ul class="divide-y divide-border">
      <li v-for="route in routes" :key="route.id">
        <RouteListItem :route="route" :units="units" />
      </li>
    </ul>
  </ListPanel>
</template>
