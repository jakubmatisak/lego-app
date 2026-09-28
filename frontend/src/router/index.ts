/**
 * Smerovanie. Verejná stránka zbierky má vlastnú cestu bez rámu appky
 * a bez kontroly prihlásenia.
 */

import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/prihlasenie',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      // Zásady ochrany súkromia: verejné, odkazuje na ne registrácia.
      path: '/sukromie',
      name: 'privacy',
      component: () => import('@/views/PrivacyView.vue'),
      meta: { public: true },
    },
    {
      // Súpis pre poistku: bez ponuky a lišty, aby sa dal rovno vytlačiť.
      path: '/supis',
      name: 'inventory',
      component: () => import('@/views/InventoryView.vue'),
    },
    {
      path: '/z/:token',
      name: 'public-collection',
      component: () => import('@/views/PublicCollectionView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'zbierka',
          name: 'collection',
          component: () => import('@/views/CollectionView.vue'),
          // Na širokej obrazovke presne na výšku okna, posúvajú sa len karty.
          meta: { fitScreen: true },
        },
        {
          path: 'figurky',
          name: 'minifigs',
          component: () => import('@/views/MinifigsView.vue'),
        },
        {
          path: 'figurky/:num',
          name: 'minifig-series',
          component: () => import('@/views/MinifigSeriesView.vue'),
        },
        {
          path: 'temy',
          name: 'themes',
          component: () => import('@/views/ThemesView.vue'),
        },
        {
          path: 'temy/:theme',
          name: 'theme',
          component: () => import('@/views/ThemeView.vue'),
        },
        {
          path: 'pridat',
          name: 'add-set',
          component: () => import('@/views/AddSetView.vue'),
        },
        {
          path: 'set/:num',
          name: 'set-detail',
          component: () => import('@/views/SetDetailView.vue'),
        },
        {
          path: 'chcem',
          name: 'wishlist',
          component: () => import('@/views/WishlistView.vue'),
        },
        {
          path: 'overit-cenu',
          name: 'price-check',
          component: () => import('@/views/PriceCheckView.vue'),
          meta: { fitScreen: true },
        },
        {
          path: 'nastavenia',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: { name: 'dashboard' },
    },
  ],
})

router.beforeEach(async to => {
  if (to.meta.public) {
    return true
  }

  const auth = useAuthStore()
  if (!auth.ready) {
    await auth.restore()
  }
  if (auth.isLoggedIn) {
    return true
  }

  return { name: 'login', query: { redirect: to.fullPath } }
})

export default router
