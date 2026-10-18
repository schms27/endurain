<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Medal } from '@lucide/vue'

import { medalFor } from '@/features/segments/utils/segments'

const props = defineProps<{
  /** A 1-based rank; only ranks 1 to 3 earn a medal. */
  rank: number | null
}>()

const { t } = useI18n()

const medal = computed(() => medalFor(props.rank))

const MEDAL_CLASSES = {
  gold: 'text-effort',
  silver: 'text-muted-foreground',
  bronze: 'text-hr',
} as const
</script>

<template>
  <span
    v-if="medal"
    class="flex shrink-0 items-center gap-1 text-xs font-medium"
    :class="MEDAL_CLASSES[medal]"
  >
    <Medal class="size-5" aria-hidden="true" />
    <span>{{ t(`segments.medal.${medal}`) }}</span>
  </span>
</template>
