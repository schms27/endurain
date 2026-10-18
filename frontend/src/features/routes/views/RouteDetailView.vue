<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { ArrowLeft, BookmarkPlus, Download, Pencil, Share2, Trash2 } from '@lucide/vue'

import type { PublicRoute, RouteDetail } from '@/features/routes/types'
import type { SharedRouteRef } from '@/features/routes/services/routes'

import RouteDetailContent from '@/features/routes/components/RouteDetailContent.vue'
import RouteEditDialog from '@/features/routes/components/RouteEditDialog.vue'
import RouteShareDialog from '@/features/routes/components/RouteShareDialog.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorState } from '@/components/ui/error-state'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuthStore } from '@/features/auth/stores/auth'
import { useCurrentUser } from '@/features/auth/composables/useCurrentUser'
import { useDisplayUnits } from '@/features/activities/composables/useActivityDetail'
import { useToasts } from '@/composables/useToasts'
import { downloadBlob } from '@/lib/download'
import {
  useCopyRouteMutation,
  useDeleteRouteMutation,
  useRouteQuery,
  useSharedRouteQuery,
} from '@/features/routes/composables/useRoutes'
import { exportRouteGpx, exportSharedRouteGpx } from '@/features/routes/services/routes'
import { ROUTE_SOURCE, ROUTE_VISIBILITY } from '@/features/routes/types'

const currentRoute = useRoute()
const router = useRouter()
const { t } = useI18n()
const toasts = useToasts()
const { isAuthenticated } = storeToRefs(useAuthStore())
const { data: currentUser } = useCurrentUser()
const units = useDisplayUnits()

// `/r/:token` opens a route through its unlisted link; `/route/:id` reads it
// as the signed-in viewer, or as a public route for anonymous visitors.
const shareToken = computed(() =>
  typeof currentRoute.params.token === 'string' && currentRoute.params.token
    ? currentRoute.params.token
    : null,
)
const routeId = computed(() => {
  const raw = Number(currentRoute.params.id)
  return Number.isFinite(raw) && raw > 0 ? raw : null
})
const sharedRef = computed<SharedRouteRef | null>(() => {
  if (shareToken.value) {
    return { token: shareToken.value }
  }
  return !isAuthenticated.value && routeId.value !== null ? { publicId: routeId.value } : null
})

const ownQuery = useRouteQuery(() => (shareToken.value ? null : routeId.value))
const sharedQuery = useSharedRouteQuery(sharedRef)

const plannedRoute = computed<RouteDetail | PublicRoute | undefined>(() =>
  sharedRef.value ? sharedQuery.data.value : ownQuery.data.value,
)
const isPending = computed(() =>
  sharedRef.value ? sharedQuery.isPending.value : ownQuery.isPending.value,
)
const isError = computed(() =>
  sharedRef.value ? sharedQuery.isError.value : ownQuery.isError.value,
)
const isNotFound = computed(() => {
  const error = sharedRef.value ? sharedQuery.error.value : ownQuery.error.value
  const status = (error as { status?: number } | null)?.status
  return isError.value && (status === 404 || status === 422)
})
function refetch(): void {
  void (sharedRef.value ? sharedQuery.refetch() : ownQuery.refetch())
}

const isOwner = computed(() => {
  const value = plannedRoute.value
  if (!value) {
    return false
  }
  return value.isOwner || (currentUser.value !== undefined && value.userId === currentUser.value.id)
})
const canCopy = computed(() => isAuthenticated.value && !!plannedRoute.value && !isOwner.value)
const creator = computed(() =>
  plannedRoute.value && 'owner' in plannedRoute.value ? plannedRoute.value.owner : null,
)
const visibilityLabel = computed(() => {
  switch (plannedRoute.value?.visibility) {
    case ROUTE_VISIBILITY.public:
      return t('routes.share.visibility.public')
    case ROUTE_VISIBILITY.followers:
      return t('routes.share.visibility.followers')
    default:
      return t('routes.share.visibility.private')
  }
})

const isExporting = ref(false)
async function downloadGpx(): Promise<void> {
  const value = plannedRoute.value
  if (!value) {
    return
  }
  isExporting.value = true
  try {
    const blob = sharedRef.value
      ? await exportSharedRouteGpx(sharedRef.value)
      : await exportRouteGpx(value.id)
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

const copyMutation = useCopyRouteMutation()
function saveCopy(): void {
  const value = plannedRoute.value
  if (!value) {
    return
  }
  copyMutation.mutate(shareToken.value ? { token: shareToken.value } : { id: value.id }, {
    onSuccess: (copy) => {
      toasts.success(t('routes.copy.success'))
      void router.push({ name: 'route', params: { id: copy.id } })
    },
    onError: () => {
      toasts.error(t('routes.copy.error'))
    },
  })
}

const isEditOpen = ref(false)
const isShareOpen = ref(false)
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
    <Button
      v-if="isAuthenticated"
      variant="ghost"
      size="sm"
      class="self-start"
      @click="router.push({ name: 'routes' })"
    >
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
      :description="
        sharedRef ? t('routes.detail.sharedNotFound') : t('routes.detail.notFoundDescription')
      "
    >
      <template v-if="isAuthenticated" #action>
        <Button variant="outline" @click="router.push({ name: 'routes' })">
          {{ t('routes.detail.back') }}
        </Button>
      </template>
    </EmptyState>

    <ErrorState
      v-else-if="isError || !plannedRoute"
      :title="t('routes.error.title')"
      :description="t('routes.error.description')"
      @retry="refetch"
    >
      <template #action="{ retry }">
        <Button variant="outline" @click="retry">{{ t('routes.error.retry') }}</Button>
      </template>
    </ErrorState>

    <template v-else>
      <header class="flex flex-wrap items-start justify-between gap-3">
        <div class="flex min-w-0 flex-col gap-1">
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="text-page-title break-words">{{ plannedRoute.name }}</h1>
            <Badge v-if="isOwner" variant="outline" data-testid="route-visibility">
              {{ visibilityLabel }}
            </Badge>
          </div>
          <p
            v-if="
              isOwner &&
              plannedRoute.source === ROUTE_SOURCE.activity &&
              plannedRoute.sourceActivityId
            "
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
          <p v-else-if="isOwner && plannedRoute.source === ROUTE_SOURCE.copy" class="text-body">
            {{ t('routes.detail.copied') }}
          </p>
          <p v-else-if="isOwner && plannedRoute.originalFilename" class="text-body">
            {{ t('routes.detail.importedFrom', { filename: plannedRoute.originalFilename }) }}
          </p>
          <p v-else-if="creator" class="text-body" data-testid="route-creator">
            {{ t('routes.detail.createdBy', { name: creator.name }) }}
          </p>
          <p v-else-if="isAuthenticated && !isOwner" class="text-body">
            <RouterLink
              :to="{ name: 'user', params: { id: plannedRoute.userId } }"
              class="underline"
            >
              {{ t('routes.detail.viewCreator') }}
            </RouterLink>
          </p>
          <p v-if="!isOwner && plannedRoute.hideEndpointsM > 0" class="text-hint">
            {{ t('routes.detail.endpointsHidden') }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button
            v-if="plannedRoute.points.length > 0"
            variant="outline"
            size="sm"
            :disabled="isExporting"
            @click="downloadGpx"
          >
            <Download class="size-4" aria-hidden="true" />
            {{ t('routes.actions.export') }}
          </Button>
          <Button
            v-if="canCopy"
            size="sm"
            :disabled="copyMutation.isPending.value || plannedRoute.points.length < 2"
            @click="saveCopy"
          >
            <BookmarkPlus class="size-4" aria-hidden="true" />
            {{ t('routes.actions.copy') }}
          </Button>
          <template v-if="isOwner && !sharedRef">
            <Button variant="outline" size="sm" @click="isShareOpen = true">
              <Share2 class="size-4" aria-hidden="true" />
              {{ t('routes.actions.share') }}
            </Button>
            <Button variant="outline" size="sm" @click="isEditOpen = true">
              <Pencil class="size-4" aria-hidden="true" />
              {{ t('routes.actions.edit') }}
            </Button>
            <Button variant="ghostDestructive" size="sm" @click="isDeleteOpen = true">
              <Trash2 class="size-4" aria-hidden="true" />
              {{ t('routes.actions.delete') }}
            </Button>
          </template>
        </div>
      </header>

      <RouteDetailContent :route="plannedRoute" :units="units" />

      <template v-if="isOwner && !sharedRef">
        <RouteShareDialog v-model:open="isShareOpen" :route="plannedRoute" :units="units" />
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
    </template>
  </section>
</template>
