import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import { mount } from '@vue/test-utils'

import type { RouteDetail, RouteHomeWarning } from '@/features/routes/types'

import i18n from '@/i18n'
import RouteShareDialog from '@/features/routes/components/RouteShareDialog.vue'

const homeWarning = ref<RouteHomeWarning | undefined>(undefined)
const updateMutate = vi.fn<(...args: unknown[]) => void>()
const createMutate = vi.fn<(...args: unknown[]) => void>()
const revokeMutate = vi.fn<(...args: unknown[]) => void>()

vi.mock('@/features/routes/composables/useRoutes', () => ({
  useRouteHomeWarningQuery: () => ({ data: homeWarning }),
  useUpdateRouteSharingMutation: () => ({ mutate: updateMutate, isPending: ref(false) }),
  useCreateRouteShareTokenMutation: () => ({ mutate: createMutate, isPending: ref(false) }),
  useRevokeRouteShareTokenMutation: () => ({ mutate: revokeMutate, isPending: ref(false) }),
}))

vi.mock('@/composables/useToasts', () => ({
  useToasts: () => ({
    success: vi.fn<(message: string) => void>(),
    error: vi.fn<(message: string) => void>(),
  }),
}))

/** Passthrough stub so the reka-ui portal/focus-trap is skipped. */
const passthrough = { template: '<div><slot /></div>' }

function route(overrides: Partial<RouteDetail> = {}): RouteDetail {
  return {
    id: 7,
    userId: 1,
    name: 'Castle loop',
    activityType: null,
    source: 1,
    visibility: 2,
    distance: 1000,
    elevationGain: null,
    elevationLoss: null,
    isLoop: false,
    city: null,
    country: null,
    createdAt: '2024-01-01T00:00:00Z',
    description: null,
    sourceActivityId: null,
    sourceRouteId: null,
    originalFilename: null,
    shareToken: null,
    hideEndpointsM: 0,
    isOwner: true,
    points: [],
    pois: [],
    elevationMin: null,
    elevationMax: null,
    ...overrides,
  }
}

function mountDialog(value: RouteDetail) {
  return mount(RouteShareDialog, {
    props: { open: true, route: value, units: 'metric' },
    global: {
      plugins: [i18n],
      stubs: {
        Dialog: passthrough,
        DialogContent: passthrough,
        DialogHeader: passthrough,
        DialogTitle: passthrough,
        DialogDescription: passthrough,
        DialogFooter: passthrough,
      },
    },
  })
}

function buttonWithText(wrapper: ReturnType<typeof mountDialog>, text: string) {
  const button = wrapper.findAll('button').find((candidate) => candidate.text().includes(text))
  if (!button) {
    throw new Error(`No button "${text}"`)
  }
  return button
}

describe('RouteShareDialog', () => {
  beforeEach(() => {
    homeWarning.value = undefined
    updateMutate.mockReset()
    createMutate.mockReset()
    revokeMutate.mockReset()
  })

  it('warns about a home-like start only once the route is shared', async () => {
    homeWarning.value = { startNearHome: true, endNearHome: false }
    const privateRoute = mountDialog(route())
    expect(privateRoute.find('[data-testid="route-home-warning"]').exists()).toBe(false)

    const publicRoute = mountDialog(route({ visibility: 0 }))
    expect(publicRoute.find('[data-testid="route-home-warning"]').text()).toContain(
      'starts near where many of your activities start',
    )

    const linked = mountDialog(route({ shareToken: 'tok' }))
    expect(linked.find('[data-testid="route-home-warning"]').exists()).toBe(true)
  })

  it('saves visibility and endpoint trimming', async () => {
    const wrapper = mountDialog(route())
    const save = buttonWithText(wrapper, 'Save')
    expect(save.attributes('disabled')).toBeDefined()

    await wrapper.find('#route-visibility').setValue('0')
    await wrapper.find('#route-hide-endpoints').setValue('200')
    await save.trigger('click')

    expect(updateMutate).toHaveBeenCalledWith(
      { id: 7, input: { visibility: 0, hideEndpointsM: 200 } },
      expect.any(Object),
    )
  })

  it('creates a link when there is none', async () => {
    const wrapper = mountDialog(route())
    expect(wrapper.find('input[readonly]').exists()).toBe(false)
    await buttonWithText(wrapper, 'Create link').trigger('click')
    expect(createMutate).toHaveBeenCalledWith(7, expect.any(Object))
  })

  it('shows, rotates and revokes an existing link', async () => {
    const wrapper = mountDialog(route({ shareToken: 'tok' }))
    expect((wrapper.find('input[readonly]').element as HTMLInputElement).value).toMatch(/\/r\/tok$/)

    await buttonWithText(wrapper, 'New link').trigger('click')
    expect(createMutate).toHaveBeenCalledWith(7, expect.any(Object))

    await buttonWithText(wrapper, 'Turn off link').trigger('click')
    expect(revokeMutate).toHaveBeenCalledWith(7, expect.any(Object))
  })
})
