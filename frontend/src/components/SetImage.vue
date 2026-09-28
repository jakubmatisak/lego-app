<script setup lang="ts">
/**
 * Fotka setu z katalógu. Keď chýba alebo sa nenačíta, nakreslí sa
 * krabica, aby karta nemala prázdnu dieru.
 *
 * Fotka sa nikdy neoreže. Sety sú široké, minifigúrky vysoké a orezanie
 * na štvorec z nich ubralo práve to, podľa čoho sa poznajú.
 */
  import { ref, watch } from 'vue'
  import { imageSrc } from '@/utils/imageSrc'

  const props = withDefaults(defineProps<{
    src?: string | null
    alt?: string
    size?: number | string
    rounded?: string
  }>(), {
    src: null,
    alt: '',
    size: 128,
    rounded: 'lg',
  })

  const failed = ref(false)
  watch(() => props.src, () => {
    failed.value = false
  })
</script>

<template>
  <div
    class="set-image d-flex align-center justify-center"
    :class="`rounded-${rounded}`"
    :style="{ height: typeof size === 'number' ? `${size}px` : size }"
  >
    <v-img
      v-if="src && !failed"
      :alt="alt"
      class="set-image__photo"
      height="100%"
      :src="imageSrc(src) ?? undefined"
      width="100%"
      @error="failed = true"
    />

    <svg
      v-else
      class="set-image__placeholder"
      fill="none"
      height="52%"
      role="presentation"
      viewBox="0 0 96 96"
      width="52%"
    >
      <rect
        height="52"
        rx="4"
        stroke="currentColor"
        stroke-width="3"
        width="68"
        x="14"
        y="26"
      />

      <path d="M14 40h68" stroke="currentColor" stroke-width="3" />

      <rect
        fill="currentColor"
        height="16"
        rx="2.5"
        width="36"
        x="30"
        y="52"
      />

      <rect
        fill="currentColor"
        height="7"
        rx="1.5"
        width="8"
        x="36"
        y="46"
      />

      <rect
        fill="currentColor"
        height="7"
        rx="1.5"
        width="8"
        x="52"
        y="46"
      />
    </svg>
  </div>
</template>

<style scoped>
.set-image {
  background: rgb(var(--v-theme-surface-variant));
  overflow: hidden;
  width: 100%;
}

/* Bez orezania sa fotka dotýka okrajov, malý odstup jej pomáha. */
.set-image__photo {
  padding: 4px;
}

.set-image__placeholder {
  color: rgb(var(--v-theme-on-surface-variant));
  opacity: 0.32;
}
</style>
