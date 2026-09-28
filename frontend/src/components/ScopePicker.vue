<script setup lang="ts">
  /**
   * Rozsah Prehľadu: celá zbierka, uložený pohľad, kategória, zoznam alebo
   * téma. Keď je rozsah zapnutý, štítok s krížikom nad dlaždicami hovorí,
   * že čísla nie sú za celú zbierku.
   */
  import type { Scope } from '@/utils/scope'
  import { computed, onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { PURPOSES } from '@/api/types'
  import { useCollectionStore } from '@/stores/collection'
  import { useFilterStore } from '@/stores/filters'
  import { scopeFromCategory, scopeFromPurpose, scopeFromTheme, scopeFromView } from '@/utils/scope'

  defineProps<{ scope: Scope | null }>()
  const emit = defineEmits<{ update: [scope: Scope | null] }>()

  const { t } = useI18n()
  const filters = useFilterStore()
  const collection = useCollectionStore()

  /** Témy celej zbierky, od najväčšej. */
  const themes = computed(() => (collection.summary?.themes ?? []).map(slice => ({ key: slice.key, label: slice.theme })))

  onMounted(() => {
    if (filters.views.length === 0) filters.loadViews()
    if (filters.categories.length === 0) filters.loadCategories()
  })
</script>

<template>
  <div class="d-flex align-center flex-wrap ga-2">
    <v-menu max-height="480">
      <template #activator="{ props: menu }">
        <v-btn
          v-bind="menu"
          append-icon="mdi-menu-down"
          prepend-icon="mdi-filter-variant"
          size="small"
          variant="outlined"
        >{{ t('scope.label') }}: {{ scope?.label ?? t('scope.all') }}</v-btn>
      </template>

      <v-list density="compact">
        <v-list-item :active="scope === null" :title="t('scope.all')" @click="emit('update', null)" />

        <template v-if="filters.views.length > 0">
          <v-list-subheader>{{ t('scope.views') }}</v-list-subheader>

          <v-list-item
            v-for="view in filters.views"
            :key="`v${view.id}`"
            :active="scope?.kind === 'view' && scope.id === String(view.id)"
            :title="view.name"
            @click="emit('update', scopeFromView(view))"
          />
        </template>

        <template v-if="filters.categories.length > 0">
          <v-list-subheader>{{ t('scope.categories') }}</v-list-subheader>

          <v-list-item
            v-for="category in filters.categories"
            :key="`c${category.id}`"
            :active="scope?.kind === 'category' && scope.id === String(category.id)"
            :title="category.name"
            @click="emit('update', scopeFromCategory(category))"
          />
        </template>

        <v-list-subheader>{{ t('scope.purposes') }}</v-list-subheader>

        <v-list-item
          v-for="purpose in PURPOSES"
          :key="`p${purpose}`"
          :active="scope?.kind === 'purpose' && scope.id === purpose"
          :title="t(`purpose.${purpose}`)"
          @click="emit('update', scopeFromPurpose(purpose, t(`purpose.${purpose}`)))"
        />

        <template v-if="themes.length > 0">
          <v-list-subheader>{{ t('scope.themes') }}</v-list-subheader>

          <v-list-item
            v-for="theme in themes"
            :key="`t${theme.key}`"
            :active="scope?.kind === 'theme' && scope.id === theme.key"
            :title="theme.label"
            @click="emit('update', scopeFromTheme(theme.key, theme.label))"
          />
        </template>
      </v-list>
    </v-menu>

    <v-chip
      v-if="scope"
      closable
      color="primary"
      label
      size="small"
      variant="tonal"
      @click:close="emit('update', null)"
    >{{ t('scope.active', { label: scope.label }) }}</v-chip>

    <span v-if="scope" class="text-caption text-medium-emphasis">{{ t('scope.note') }}</span>
  </div>
</template>
