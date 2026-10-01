<script setup lang="ts">
/**
 * Kostra stránky pri prvom načítaní, v tvare toho, čo príde: dlaždice
 * a grafy Prehľadu, karty setov, riadky zoznamu, tabuľka, detail setu.
 * Prázdny stav sa ukáže až po odpovedi servera (`composables/usePageLoad.ts`).
 */
  import CardGrid from '@/components/CardGrid.vue'

  withDefaults(defineProps<{
    kind: 'dashboard' | 'cards' | 'rows' | 'table' | 'detail'
    /** Počet kariet či riadkov. */
    count?: number
  }>(), { count: 8 })
</script>

<template>
  <div aria-busy="true" class="page-skeleton" :data-kind="kind">
    <template v-if="kind === 'dashboard'">
      <v-row dense>
        <v-col
          v-for="n in 5"
          :key="n"
          cols="12"
          lg=""
          md="4"
          sm="6"
        >
          <v-card border class="pa-2" flat>
            <v-skeleton-loader type="text, heading, text" />
          </v-card>
        </v-col>
      </v-row>

      <v-row class="mt-3" dense>
        <v-col cols="12" lg="8">
          <v-card border flat>
            <v-skeleton-loader height="320" type="heading, image" />
          </v-card>
        </v-col>

        <v-col cols="12" lg="4">
          <v-card border flat>
            <v-skeleton-loader height="320" type="heading, avatar, list-item@3" />
          </v-card>
        </v-col>
      </v-row>

      <v-row class="mt-3" dense>
        <v-col
          v-for="n in 3"
          :key="n"
          cols="12"
          lg="4"
          md="6"
        >
          <v-card border flat>
            <v-skeleton-loader type="heading, list-item-avatar-two-line@4" />
          </v-card>
        </v-col>
      </v-row>
    </template>

    <CardGrid v-else-if="kind === 'cards'">
      <v-card v-for="n in count" :key="n" border flat>
        <v-skeleton-loader height="132" type="image" />
        <v-skeleton-loader type="list-item-two-line" />
      </v-card>
    </CardGrid>

    <v-card v-else-if="kind === 'rows'" border flat>
      <v-skeleton-loader :type="`list-item-two-line@${count}`" />
    </v-card>

    <v-card v-else-if="kind === 'table'" border flat>
      <v-skeleton-loader :type="`table-thead, table-row-divider@${count}`" />
    </v-card>

    <div v-else class="d-flex flex-column ga-4">
      <v-card border flat>
        <div class="d-flex flex-wrap">
          <v-skeleton-loader class="page-skeleton__photo" height="260" type="image" />
          <v-skeleton-loader class="flex-grow-1" type="heading, subtitle, chip@3, paragraph" />
        </div>
      </v-card>

      <v-card border flat>
        <v-skeleton-loader type="heading, list-item-two-line@3" />
      </v-card>
    </div>
  </div>
</template>

<style scoped>
.page-skeleton__photo {
  flex: 0 0 320px;
  max-width: 100%;
}
</style>
