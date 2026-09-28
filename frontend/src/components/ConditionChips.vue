<script setup lang="ts">
/** Stav kusu, jeho príznaky a umiestnenie ako rad čipov. */
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'

  import { NEGATIVE_FLAGS } from '@/api/types'

  const props = withDefaults(defineProps<{
    condition?: string | null
    flags?: string[] | null
    location?: string | null
    variant?: string | null
    size?: 'x-small' | 'small' | 'default'
    highlightCondition?: boolean
  }>(), {
    condition: null,
    flags: () => [],
    location: null,
    variant: null,
    size: 'small',
    highlightCondition: true,
  })

  const { t } = useI18n()

  const conditionLabel = computed(() =>
    props.condition ? t(`condition.${props.condition}`) : null,
  )
  const variantLabel = computed(() =>
    props.variant ? t(`variant.${props.variant}`) : null,
  )
</script>

<template>
  <div class="d-flex flex-wrap ga-1">
    <v-chip
      v-if="conditionLabel"
      :color="highlightCondition && condition === 'new_sealed' ? 'primary' : undefined"
      label
      :size="size"
      :variant="highlightCondition && condition === 'new_sealed' ? 'tonal' : 'tonal'"
    >{{ conditionLabel }}</v-chip>

    <v-chip v-if="variantLabel" label :size="size" variant="tonal">{{ variantLabel }}</v-chip>

    <v-chip
      v-for="flag in flags ?? []"
      :key="flag"
      :color="NEGATIVE_FLAGS.includes(flag) ? 'negative' : undefined"
      label
      :size="size"
      variant="tonal"
    >{{ t(`flag.${flag}`) }}</v-chip>

    <v-chip
      v-if="location"
      label
      prepend-icon="mdi-map-marker-outline"
      :size="size"
      variant="tonal"
    >
      {{ location }}
    </v-chip>
  </div>
</template>
