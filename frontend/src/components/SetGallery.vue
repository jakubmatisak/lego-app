<script setup lang="ts">
  /**
   * Ďalšie oficiálne fotky setu z Brickset. Server ich stiahne raz na set
   * (do limitu Brickset sa nerátajú) a potom ich dáva z databázy. Prepínač
   * v Nastaveniach → Dáta galériu vypne celú. Obrázky sa načítavajú priamo
   * z Brickset a podľa jeho podmienok nesú poďakovanie pod galériou.
   */
  import type { SetImage } from '@/api/types'
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import ImageViewer from '@/components/ImageViewer.vue'
  import SourceCredit from '@/components/SourceCredit.vue'
  import { imageSrc } from '@/utils/imageSrc'

  /** `mainImage`: hlavná fotka z katalógu, v okne ide pred fotkami z Brickset. */
  const props = defineProps<{ num: string, name: string, mainImage?: string | null }>()

  const { t } = useI18n()
  const images = ref<SetImage[]>([])
  const open = ref(false)
  const current = ref(0)

  const viewerImages = computed(() => [
    ...(props.mainImage ? [{ url: props.mainImage }] : []),
    ...images.value.map(image => ({ url: image.image_url, credit: t('detail.galleryCredit') })),
  ])

  function show (index: number): void {
    current.value = index + (props.mainImage ? 1 : 0)
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

    <ImageViewer v-model:index="current" v-model:open="open" :images="viewerImages" :name="name" />
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
