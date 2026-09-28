<script setup lang="ts">
  /**
   * Najväčšie pohyby trhovej ceny. Položka bez staršej snímky sa
   * nezobrazí, nič sa nedopočítava.
   */
  import type { Mover } from '@/api/types'
  import { ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { exactMoney, percent } from '@/utils/format'

  const props = defineProps<{ movers: Mover[] }>()
  const emit = defineEmits<{ (e: 'window', value: 30 | 90 | 365): void }>()

  const { t } = useI18n()
  const windowDays = ref<30 | 90 | 365>(90)

  watch(windowDays, value => emit('window', value))
</script>

<template>
  <v-card border class="h-100 d-flex flex-column" flat>
    <v-card-item class="pb-2">
      <div class="d-flex align-center ga-3">
        <v-card-title class="text-h6 pa-0">{{ t('dashboard.movers') }}</v-card-title>

        <v-btn-toggle
          v-model="windowDays"
          class="ms-auto"
          density="compact"
          mandatory
          variant="outlined"
        >
          <v-btn size="small" :value="30">{{ t('detail.day30') }}</v-btn>
          <v-btn size="small" :value="90">{{ t('detail.day90') }}</v-btn>
          <v-btn size="small" :value="365">{{ t('detail.year') }}</v-btn>
        </v-btn-toggle>
      </div>
    </v-card-item>

    <v-list v-if="props.movers.length > 0" density="comfortable" lines="two">
      <v-list-item
        v-for="mover in props.movers"
        :key="mover.catalog_num"
        :to="{ name: 'set-detail', params: { num: mover.catalog_num } }"
      >
        <v-list-item-title class="text-body-2 font-weight-medium">
          {{ mover.name }}
        </v-list-item-title>

        <v-list-item-subtitle class="text-caption">
          {{ exactMoney(mover.price_then) }} → {{ exactMoney(mover.price_now) }}
        </v-list-item-subtitle>

        <template #append>
          <v-chip
            :color="mover.delta_pct >= 0 ? 'positive' : 'negative'"
            :prepend-icon="mover.delta_pct >= 0 ? 'mdi-arrow-up' : 'mdi-arrow-down'"
            size="small"
            variant="tonal"
          >
            {{ percent(mover.delta_pct) }}
          </v-chip>
        </template>
      </v-list-item>
    </v-list>

    <v-card-text v-else class="text-body-2 text-medium-emphasis">
      {{ t('dashboard.moversEmpty') }}
    </v-card-text>
  </v-card>
</template>
