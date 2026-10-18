<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileUp, Route as RouteIcon, Search, X } from '@lucide/vue'

import RouteImportDialog from '@/features/routes/components/RouteImportDialog.vue'
import RouteListItem from '@/features/routes/components/RouteListItem.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { ListPanel } from '@/components/ui/list-panel'
import { Skeleton } from '@/components/ui/skeleton'
import { useCurrentUser } from '@/features/auth/composables/useCurrentUser'
import { useRecordsPerPage } from '@/features/config/composables/useRecordsPerPage'
import { useListPagination } from '@/composables/useListPagination'
import { useToasts } from '@/composables/useToasts'
import { useRoutesQuery } from '@/features/routes/composables/useRoutes'

const { t } = useI18n()
const toasts = useToasts()
const { data: currentUser } = useCurrentUser()
const units = computed(() => currentUser.value?.units ?? 'metric')

const page = ref(1)
const searchTerm = ref('')
const debouncedSearch = ref('')
const { recordsPerPage } = useRecordsPerPage()

// Debounce the name search so typing doesn't fire a request per keystroke.
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(searchTerm, (value) => {
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    debouncedSearch.value = value
  }, 400)
})
onBeforeUnmount(() => {
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
})

function clearSearch(): void {
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  searchTerm.value = ''
  debouncedSearch.value = ''
}

const isSearching = computed(() => debouncedSearch.value.trim().length > 0)
const query = useRoutesQuery(page, recordsPerPage, debouncedSearch)
const routes = computed(() => query.data.value?.records ?? [])
const totalCount = computed(() => query.data.value?.total ?? 0)
const { totalPages, reset: resetPage } = useListPagination(page, totalCount, recordsPerPage)
watch(debouncedSearch, resetPage)

const isEmpty = computed(
  () => !query.isPending.value && !query.isError.value && routes.value.length === 0,
)

const isImportOpen = ref(false)
</script>

<template>
  <section class="flex flex-col gap-3">
    <header class="flex flex-col gap-1">
      <h1 class="text-page-title">{{ t('routes.title') }}</h1>
      <p class="text-body">{{ t('routes.subtitle') }}</p>
    </header>

    <div class="grid gap-3 lg:grid-cols-[18rem_minmax(0,1fr)] lg:items-start">
      <aside class="lg:sticky lg:top-6">
        <Card class="flex flex-col gap-3">
          <Button class="w-full" @click="isImportOpen = true">
            <FileUp class="size-4" aria-hidden="true" />
            {{ t('routes.buttonImport') }}
          </Button>
          <div class="relative">
            <Search
              class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              v-model="searchTerm"
              type="search"
              :placeholder="t('routes.searchPlaceholder')"
              :aria-label="t('routes.searchPlaceholder')"
              class="w-full pl-9 pr-9"
            />
            <button
              v-if="searchTerm"
              type="button"
              class="absolute right-1 top-1/2 inline-flex size-7 -translate-y-1/2 items-center justify-center rounded-input text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
              :aria-label="t('routes.clearSearch')"
              @click="clearSearch"
            >
              <X class="size-4" aria-hidden="true" />
            </button>
          </div>
        </Card>
      </aside>

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
            <div v-for="n in 6" :key="n" class="flex items-center gap-3 px-4 py-3">
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
            :title="isSearching ? t('routes.empty.searchTitle') : t('routes.empty.title')"
            :description="
              isSearching ? t('routes.empty.searchDescription') : t('routes.empty.description')
            "
            :variant="isSearching ? 'filtered' : 'first-time'"
          >
            <template #icon>
              <RouteIcon class="size-8" aria-hidden="true" />
            </template>
            <template v-if="!isSearching" #action>
              <Button @click="isImportOpen = true">
                <FileUp class="size-4" aria-hidden="true" />
                {{ t('routes.buttonImport') }}
              </Button>
            </template>
          </EmptyState>
        </template>

        <ul class="divide-y divide-border">
          <li v-for="route in routes" :key="route.id">
            <RouteListItem :route="route" :units="units" />
          </li>
        </ul>
      </ListPanel>
    </div>

    <RouteImportDialog
      v-model:open="isImportOpen"
      @success="toasts.success"
      @error="toasts.error"
    />
  </section>
</template>
