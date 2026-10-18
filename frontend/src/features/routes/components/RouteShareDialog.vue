<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy, Link, RefreshCw, Unlink } from '@lucide/vue'

import type { Units } from '@/features/activities/utils/format'
import type { RouteDetail, RouteVisibility } from '@/features/routes/types'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useToasts } from '@/composables/useToasts'
import { combineMetric, formatElevation } from '@/features/activities/utils/format'
import {
  useCreateRouteShareTokenMutation,
  useRevokeRouteShareTokenMutation,
  useRouteHomeWarningQuery,
  useUpdateRouteSharingMutation,
} from '@/features/routes/composables/useRoutes'
import { routeShareUrl } from '@/features/routes/services/routes'
import { HIDE_ENDPOINTS_OPTIONS, ROUTE_VISIBILITY } from '@/features/routes/types'

const open = defineModel<boolean>('open', { required: true })
const props = defineProps<{ route: RouteDetail; units: Units }>()

const { t } = useI18n()
const toasts = useToasts()

const visibility = ref<RouteVisibility>(props.route.visibility)
const hideEndpointsM = ref<number>(props.route.hideEndpointsM)

// Re-seed from the route each time the dialog opens.
watch(open, (isOpen) => {
  if (isOpen) {
    visibility.value = props.route.visibility
    hideEndpointsM.value = props.route.hideEndpointsM
  }
})

const visibilityOptions = computed(() => [
  { value: ROUTE_VISIBILITY.private, label: t('routes.share.visibility.private') },
  { value: ROUTE_VISIBILITY.followers, label: t('routes.share.visibility.followers') },
  { value: ROUTE_VISIBILITY.public, label: t('routes.share.visibility.public') },
])
const visibilityHint = computed(() => {
  switch (visibility.value) {
    case ROUTE_VISIBILITY.public:
      return t('routes.share.visibility.publicHint')
    case ROUTE_VISIBILITY.followers:
      return t('routes.share.visibility.followersHint')
    default:
      return t('routes.share.visibility.privateHint')
  }
})

const hideOptions = computed(() => {
  const values = new Set<number>([...HIDE_ENDPOINTS_OPTIONS, props.route.hideEndpointsM])
  return [...values]
    .sort((a, b) => a - b)
    .map((meters) => ({
      value: meters,
      label:
        meters === 0
          ? t('routes.share.hideEndpoints.none')
          : combineMetric(formatElevation(meters, props.units)),
    }))
})

const isDirty = computed(
  () =>
    visibility.value !== props.route.visibility ||
    hideEndpointsM.value !== props.route.hideEndpointsM,
)

const updateMutation = useUpdateRouteSharingMutation()
const createTokenMutation = useCreateRouteShareTokenMutation()
const revokeTokenMutation = useRevokeRouteShareTokenMutation()
const isBusy = computed(
  () =>
    updateMutation.isPending.value ||
    createTokenMutation.isPending.value ||
    revokeTokenMutation.isPending.value,
)

function save(): void {
  updateMutation.mutate(
    {
      id: props.route.id,
      input: { visibility: visibility.value, hideEndpointsM: hideEndpointsM.value },
    },
    {
      onSuccess: () => toasts.success(t('routes.share.saved')),
      onError: () => toasts.error(t('routes.share.saveError')),
    },
  )
}

const shareUrl = computed(() =>
  props.route.shareToken ? routeShareUrl(props.route.shareToken) : '',
)

function createLink(): void {
  createTokenMutation.mutate(props.route.id, {
    onError: () => toasts.error(t('routes.share.link.error')),
  })
}

function revokeLink(): void {
  revokeTokenMutation.mutate(props.route.id, {
    onSuccess: () => toasts.success(t('routes.share.link.revoked')),
    onError: () => toasts.error(t('routes.share.link.error')),
  })
}

async function copyLink(): Promise<void> {
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    toasts.success(t('routes.share.link.copied'))
  } catch {
    toasts.error(t('routes.share.link.copyError'))
  }
}

// The warning only matters once someone else can see the route.
const isShared = computed(
  () => props.route.visibility !== ROUTE_VISIBILITY.private || props.route.shareToken !== null,
)
const homeWarningQuery = useRouteHomeWarningQuery(
  () => props.route.id,
  () => open.value,
)
const homeWarning = computed(() => {
  const warning = homeWarningQuery.data.value
  if (!warning || !isShared.value) {
    return null
  }
  if (warning.startNearHome && warning.endNearHome) {
    return t('routes.share.homeWarning.both')
  }
  if (warning.startNearHome) {
    return t('routes.share.homeWarning.start')
  }
  return warning.endNearHome ? t('routes.share.homeWarning.end') : null
})
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent :close-label="t('routes.share.close')">
      <DialogHeader>
        <DialogTitle>{{ t('routes.share.title') }}</DialogTitle>
        <DialogDescription>{{ t('routes.share.description') }}</DialogDescription>
      </DialogHeader>

      <Alert v-if="homeWarning" kind="warning" class="mt-4" data-testid="route-home-warning">
        {{ homeWarning }}
      </Alert>

      <div class="mt-4 flex flex-col gap-4">
        <div class="flex flex-col gap-1.5">
          <Label for="route-visibility">{{ t('routes.share.visibility.label') }}</Label>
          <Select id="route-visibility" v-model="visibility" class="w-full" :disabled="isBusy">
            <option v-for="option in visibilityOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </Select>
          <p class="text-hint">{{ visibilityHint }}</p>
        </div>

        <div class="flex flex-col gap-1.5">
          <Label for="route-hide-endpoints">{{ t('routes.share.hideEndpoints.label') }}</Label>
          <Select
            id="route-hide-endpoints"
            v-model="hideEndpointsM"
            class="w-full"
            :disabled="isBusy"
          >
            <option v-for="option in hideOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </Select>
          <p class="text-hint">{{ t('routes.share.hideEndpoints.hint') }}</p>
        </div>

        <div class="flex justify-end">
          <Button :disabled="!isDirty || isBusy" @click="save">
            {{ t('routes.share.save') }}
          </Button>
        </div>

        <section class="flex flex-col gap-2 border-t border-border pt-4">
          <h3 class="font-medium text-foreground">{{ t('routes.share.link.title') }}</h3>
          <p class="text-hint">{{ t('routes.share.link.hint') }}</p>
          <template v-if="route.shareToken">
            <Input
              :model-value="shareUrl"
              readonly
              class="w-full font-mono text-sm"
              :aria-label="t('routes.share.link.title')"
            />
            <div class="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" @click="copyLink">
                <Copy class="size-4" aria-hidden="true" />
                {{ t('routes.share.link.copy') }}
              </Button>
              <Button variant="outline" size="sm" :disabled="isBusy" @click="createLink">
                <RefreshCw class="size-4" aria-hidden="true" />
                {{ t('routes.share.link.rotate') }}
              </Button>
              <Button variant="ghostDestructive" size="sm" :disabled="isBusy" @click="revokeLink">
                <Unlink class="size-4" aria-hidden="true" />
                {{ t('routes.share.link.revoke') }}
              </Button>
            </div>
          </template>
          <div v-else>
            <Button variant="outline" size="sm" :disabled="isBusy" @click="createLink">
              <Link class="size-4" aria-hidden="true" />
              {{ t('routes.share.link.create') }}
            </Button>
          </div>
        </section>
      </div>

      <DialogFooter class="mt-4">
        <Button variant="outline" @click="open = false">{{ t('routes.share.done') }}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
