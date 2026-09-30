<script setup lang="ts">
  import type { CategoryPicker } from '@/composables/useCategoryPicker'
  /**
   * Výber vlastných kategórií setu vo formulári: Pridať set aj úprava kusu.
   *
   * Stav drží `useCategoryPicker` u rodiča, lebo ten rozhoduje, kedy set
   * načítať a kedy výber zapísať (až pri uložení formulára). Tu sú čipy
   * a správca kategórií: nová alebo upravená kategória sa hneď ukáže vo
   * výbere a to, čo už používateľ zvolil, ostane.
   */
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import CategoryManager from '@/components/CategoryManager.vue'

  const props = withDefaults(defineProps<{
    picker: CategoryPicker
    hint: string
    label?: string
    /** Nadpis podľa formulára, v ktorom výber je. */
    titleClass?: string
  }>(), {
    label: undefined,
    titleClass: 'text-body-medium text-medium-emphasis',
  })
  /** Kategórie sa zmenili v správcovi; rodič obnoví, čo ich ukazuje inde. */
  const emit = defineEmits<{ managed: [] }>()

  const { t } = useI18n()
  const managerOpen = ref(false)

  const rows = computed(() => props.picker.rows.value)
  const chosen = computed({
    get: () => props.picker.chosen.value,
    set: ids => props.picker.select(ids ?? []),
  })

  async function onManaged (): Promise<void> {
    await props.picker.reload()
    emit('managed')
  }
</script>

<template>
  <div>
    <div class="d-flex align-center ga-2 mb-1">
      <span :class="titleClass">{{ label ?? t('add.categories') }}</span>
      <v-spacer />

      <v-btn
        prepend-icon="mdi-cog-outline"
        size="small"
        variant="text"
        @click="managerOpen = true"
      >{{ t('filters.manage') }}</v-btn>
    </div>

    <div class="text-body-small text-medium-emphasis mb-2">{{ hint }}</div>

    <!-- Prázdny zoznam počas čakania alebo po chybe nie je „žiadne kategórie“. -->
    <div v-if="rows.length === 0 && picker.loading.value" class="text-body-medium text-medium-emphasis">
      {{ t('categories.loading') }}
    </div>

    <v-chip-group
      v-else-if="rows.length > 0"
      v-model="chosen"
      column
      filter
      multiple
    >
      <v-chip
        v-for="row in rows"
        :key="row.id"
        label
        :title="row.reason === 'rule' ? t('categories.viaRule') : undefined"
        :value="row.id"
        variant="outlined"
      >
        <span class="cat-dot me-2" :class="`bg-${row.color ?? 'grey'}`" />
        {{ row.name }}
        <v-icon v-if="row.reason === 'rule'" class="ms-1" icon="mdi-auto-fix" size="x-small" />
      </v-chip>
    </v-chip-group>

    <div v-else-if="!picker.failed.value" class="text-body-medium text-medium-emphasis">{{ t('categories.empty') }}</div>

    <div v-if="picker.failed.value" class="d-flex align-center flex-wrap ga-2 text-body-medium">
      <span class="text-negative">{{ t('categories.loadFailed') }}</span>

      <v-btn
        prepend-icon="mdi-refresh"
        size="small"
        variant="text"
        @click="picker.reload()"
      >{{ t('common.retry') }}</v-btn>
    </div>

    <CategoryManager v-model="managerOpen" @changed="onManaged" />
  </div>
</template>

<style scoped>
.cat-dot {
  border-radius: 50%;
  display: inline-block;
  height: 8px;
  width: 8px;
}
</style>
