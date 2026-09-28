<script setup lang="ts">
  /**
   * Rozsah od–do v paneli filtrov: suma (číslo) alebo dátum.
   *
   * Hranice zbierky (najmenšia a najväčšia hodnota) sú zástupný text, nech
   * je vidno, v akom rozpätí sa dá hľadať. Prázdne pole znamená bez hranice.
   */
  import { useI18n } from 'vue-i18n'
  import DateField from '@/components/DateField.vue'

  const props = defineProps<{
    type: 'number' | 'date'
    from: number | string | null
    to: number | string | null
    lowHint?: string | null
    highHint?: string | null
    /** Jednotka za číslom, napríklad €. */
    suffix?: string
  }>()

  const emit = defineEmits<{
    'update:from': [value: number | string | null]
    'update:to': [value: number | string | null]
  }>()

  const { t } = useI18n()

  function asNumber (raw: unknown): number | null {
    const text = String(raw ?? '').replace(',', '.').trim()
    if (text === '') return null
    const value = Number(text)
    return Number.isFinite(value) ? value : null
  }

  function update (edge: 'from' | 'to', raw: unknown): void {
    const value = props.type === 'number' ? asNumber(raw) : ((raw as string | null) || null)
    if (edge === 'from') emit('update:from', value)
    else emit('update:to', value)
  }
</script>

<template>
  <div class="d-flex ga-2">
    <template v-if="type === 'date'">
      <DateField
        clearable
        density="compact"
        hide-details
        :label="t('filters.from')"
        :model-value="typeof from === 'string' ? from : null"
        :placeholder="lowHint ?? undefined"
        @update:model-value="update('from', $event)"
      />

      <DateField
        clearable
        density="compact"
        hide-details
        :label="t('filters.to')"
        :model-value="typeof to === 'string' ? to : null"
        :placeholder="highHint ?? undefined"
        @update:model-value="update('to', $event)"
      />
    </template>

    <template v-else>
      <v-text-field
        density="compact"
        hide-details
        inputmode="decimal"
        :label="t('filters.from')"
        :model-value="from ?? ''"
        :placeholder="lowHint ?? ''"
        :suffix="suffix"
        variant="outlined"
        @update:model-value="update('from', $event)"
      />

      <v-text-field
        density="compact"
        hide-details
        inputmode="decimal"
        :label="t('filters.to')"
        :model-value="to ?? ''"
        :placeholder="highHint ?? ''"
        :suffix="suffix"
        variant="outlined"
        @update:model-value="update('to', $event)"
      />
    </template>
  </div>
</template>
