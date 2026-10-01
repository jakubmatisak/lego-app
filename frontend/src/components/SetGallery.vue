<script setup lang="ts">
  /**
   * Ďalšie oficiálne fotky setu z Brickset. Server ich stiahne raz na set
   * (do limitu Brickset sa nerátajú) a potom ich dáva z databázy. Prepínač
   * v Nastaveniach → Dáta galériu vypne celú. Obrázky sa načítavajú priamo
   * z Brickset a podľa jeho podmienok nesú poďakovanie pod galériou.
   */
  import type { SetImage } from '@/api/types'
  import { onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import SourceCredit from '@/components/SourceCredit.vue'
  import { imageSrc } from '@/utils/imageSrc'

  const props = defineProps<{ num: string, name: string }>()

  const { t } = useI18n()
  const images = ref<SetImage[]>([])
  const open = ref(false)
  const current = ref(0)

  function show (index: number): void {
    current.value = index
    open.value = true
  }

  onMounted(async () => {
    const { data } = await api.GET('/catalog/{num}/images', { params: { path: { num: props.num } } })
    images.value = data?.enabled ? (data.images ?? []) : []
  })
</script>

<template>
  <div v-if="images.length > 0" class="d-flex flex-column ga-1">
    <div class="text-body-small text-medium-emphasis">
      {{ t('detail.galleryTitle', { count: images.length }) }}
    </div>

    <div class="gallery-strip d-flex ga-2">
      <button
        v-for="(image, index) in images"
        :key="image.image_url"
        class="gallery-thumb"
        :title="t('detail.galleryOpen')"
        type="button"
        @click="show(index)"
      >
        <img :alt="`${name} ${index + 1}`" loading="lazy" :src="imageSrc(image.thumbnail_url) ?? undefined">
      </button>
    </div>

    <SourceCredit href="https://brickset.com" :text="t('detail.galleryCredit')" />

    <v-dialog v-model="open" max-width="1100">
      <v-card>
        <v-carousel
          v-model="current"
          bg-color="white"
          height="min(80vh, 760px)"
          hide-delimiter-background
          :show-arrows="images.length > 1 ? 'hover' : false"
        >
          <v-carousel-item
            v-for="(image, index) in images"
            :key="image.image_url"
            :alt="`${name} ${index + 1}`"
            contain
            :src="imageSrc(image.image_url) ?? undefined"
          />
        </v-carousel>

        <v-card-actions>
          <span class="text-body-small text-medium-emphasis ps-2">{{ t('detail.galleryCredit') }}</span>
          <v-spacer />
          <v-btn variant="text" @click="open = false">{{ t('common.close') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
  .gallery-strip {
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .gallery-thumb {
    flex: 0 0 auto;
    width: 88px;
    height: 66px;
    border-radius: 8px;
    overflow: hidden;
    background: white;
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    cursor: zoom-in;
  }

  .gallery-thumb img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
</style>
