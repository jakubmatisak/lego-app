<script setup lang="ts">
  /**
   * Dátumové pole appky: Vuetify `v-date-input` s kalendárom.
   *
   * API aj formuláre držia dátum ako text `RRRR-MM-DD`, Vuetify ako `Date`.
   * Prevod ide cez miestny čas, nie cez `toISOString`: to prepočíta na UTC
   * a z polnoci 15. marca v Bratislave by urobilo 14. marca.
   *
   * Prázdne pole je prázdny reťazec. Budúci dátum sa vybrať nedá, lebo
   * kúpa aj predaj sú vždy v minulosti; `allow-future` to povolí.
   */
  import { computed } from 'vue'

  defineOptions({ inheritAttrs: false })

  const model = defineModel<string | null | undefined>({ default: '' })
  const props = defineProps<{ allowFuture?: boolean }>()

  function pad (value: number): string {
    return String(value).padStart(2, '0')
  }

  function toIso (value: Date): string {
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`
  }

  function fromIso (value: string): Date | null {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
    if (!match) return null
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  }

  const value = computed<Date | null>({
    get: () => (model.value ? fromIso(model.value) : null),
    set: next => {
      model.value = next instanceof Date && !Number.isNaN(next.getTime()) ? toIso(next) : ''
    },
  })

  const max = computed(() => (props.allowFuture ? undefined : toIso(new Date())))
</script>

<template>
  <v-date-input v-model="value" :max="max" v-bind="$attrs" />
</template>
