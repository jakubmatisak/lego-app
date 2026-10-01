<script setup lang="ts">
  /**
   * Veľké okno s fotkami setu: hlavná fotka z katalógu a ďalšie z Brickset.
   * Pri fotke, ktorá to vyžaduje (Brickset), je dole jej poďakovanie.
   */
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { imageSrc } from '@/utils/imageSrc'

  export interface ViewerImage {
    url: string
    credit?: string | null
  }

  const props = defineProps<{ images: ViewerImage[], name: string }>()
  const open = defineModel<boolean>('open', { default: false })
  const current = defineModel<number>('index', { default: 0 })

  const { t } = useI18n()
  const credit = computed(() => props.images[current.value]?.credit ?? null)
</script>

<template>
  <v-dialog v-model="open" max-width="1100">
    <v-card>
      <v-carousel
        v-model="current"
        bg-color="white"
        height="min(80vh, 760px)"
        hide-delimiter-background
        :hide-delimiters="images.length < 2"
        :show-arrows="images.length > 1 ? 'hover' : false"
      >
        <v-carousel-item
          v-for="(image, index) in images"
          :key="image.url"
          :alt="`${name} ${index + 1}`"
          contain
          :src="imageSrc(image.url) ?? undefined"
        />
      </v-carousel>

      <v-card-actions>
        <span v-if="credit" class="text-body-small text-medium-emphasis ps-2">{{ credit }}</span>
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.close') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
