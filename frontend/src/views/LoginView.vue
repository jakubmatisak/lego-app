<script setup lang="ts">
/** Prihlásenie a registrácia na jednej obrazovke. */
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'

  import { useAuthStore } from '@/stores/auth'
  import { safeRedirect } from '@/utils/navigation'

  const { t } = useI18n()
  const auth = useAuthStore()
  const router = useRouter()
  const route = useRoute()

  const mode = ref<'login' | 'register'>('login')
  const email = ref('')
  const password = ref('')
  const displayName = ref('')
  const showPassword = ref(false)

  /**
   * Kým server neodpovie, registráciu neponúkať: zatvorenú by používateľ
   * inak zbadal až po vyplnení formulára. Stav sa pýta tu, lebo na verejnú
   * stránku sa relácia neobnovuje a nikto iný by ho nenačítal.
   */
  const registrationOpen = computed(() => auth.providers?.registration_open === true)
  onMounted(() => {
    auth.loadProviders()
  })
  const isRegister = computed(() => mode.value === 'register')

  /** Registrácia: prečítal si zásady ochrany súkromia (povinné). */
  const privacyRead = ref(false)
  /**
   * Zapamätať si prihlásenie na tomto počítači: cookie na 30 dní namiesto
   * do zatvorenia prehliadača. Predvolene nie, aj pri registrácii: na
   * cudzom či spoločnom počítači by inak ostal účet otvorený.
   */
  const remember = ref(false)
  const canSubmit = computed(() =>
    email.value.includes('@')
    && password.value.length >= (isRegister.value ? 8 : 1)
    && (!isRegister.value || privacyRead.value),
  )

  /** Jednorazová poznámka o cookies; zavretie sa zapamätá v prehliadači. */
  const NOTE_KEY = 'moje-kocky.cookie-note'
  const cookieNote = ref(readNote())
  function readNote (): boolean {
    try {
      return localStorage.getItem(NOTE_KEY) !== '1'
    } catch {
      return true
    }
  }
  function closeNote (): void {
    cookieNote.value = false
    try {
      localStorage.setItem(NOTE_KEY, '1')
    } catch {
      // Súkromné okno: poznámka sa ukáže znova, nič viac.
    }
  }

  async function submit (): Promise<void> {
    const target = router.resolve(safeRedirect(route.query.redirect as string | undefined)).href
    await auth.signIn(isRegister.value ? 'register' : 'login', email.value, password.value, displayName.value, target, remember.value)
  }
</script>

<template>
  <v-app>
    <v-main class="d-flex align-center justify-center bg-background">
      <v-card
        border
        class="pa-6 ma-4"
        flat
        max-width="440"
        width="100%"
      >
        <div class="d-flex align-center ga-3 mb-2">
          <v-icon color="primary" icon="mdi-toy-brick" size="32" />

          <div>
            <div class="text-headline-small font-weight-bold">{{ t('app.name') }}</div>
            <div class="text-body-small text-medium-emphasis">{{ t('app.tagline') }}</div>
          </div>
        </div>

        <!-- Pri zatvorenej registrácii (rozhoduje správca v Nastaveniach) nie je čo prepínať. -->
        <v-tabs
          v-if="registrationOpen"
          v-model="mode"
          class="mb-4"
          density="comfortable"
          grow
        >
          <v-tab value="login">{{ t('auth.loginTitle') }}</v-tab>
          <v-tab value="register">{{ t('auth.registerTitle') }}</v-tab>
        </v-tabs>

        <div v-else class="text-title-large font-weight-medium mb-4">{{ t('auth.loginTitle') }}</div>

        <v-alert v-if="auth.error" class="mb-4" type="error" variant="tonal">
          {{ auth.error }}
        </v-alert>

        <v-alert
          v-if="isRegister && !registrationOpen"
          class="mb-4"
          type="info"
          variant="tonal"
        >{{ t('auth.registerClosed') }}</v-alert>

        <v-form class="d-flex flex-column ga-3" @submit.prevent="submit">
          <v-text-field
            v-if="isRegister"
            v-model="displayName"
            :label="t('auth.displayName')"
            prepend-inner-icon="mdi-account-outline"
          />

          <v-text-field
            v-model="email"
            autocomplete="email"
            autofocus
            :label="t('auth.email')"
            prepend-inner-icon="mdi-email-outline"
            type="email"
          />

          <v-text-field
            v-model="password"
            :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
            :autocomplete="isRegister ? 'new-password' : 'current-password'"
            :hint="isRegister ? t('auth.passwordHint') : undefined"
            :label="t('auth.password')"
            prepend-inner-icon="mdi-lock-outline"
            :type="showPassword ? 'text' : 'password'"
            @click:append-inner="showPassword = !showPassword"
          />

          <v-checkbox
            v-if="isRegister"
            v-model="privacyRead"
            density="compact"
            hide-details
          >
            <template #label>
              <span class="text-body-medium">
                {{ t('auth.privacyRead') }}
                <router-link target="_blank" to="/sukromie" @click.stop>{{ t('privacy.title') }}</router-link>
              </span>
            </template>
          </v-checkbox>

          <v-checkbox
            v-model="remember"
            density="compact"
            hide-details
          >
            <template #label>
              <span class="text-body-medium">{{ t('auth.remember') }}</span>
            </template>
          </v-checkbox>

          <v-btn
            block
            color="primary"
            :disabled="!canSubmit"
            :loading="auth.loading"
            size="large"
            type="submit"
          >{{ isRegister ? t('auth.register') : t('auth.login') }}</v-btn>
        </v-form>

        <div v-if="isRegister" class="text-body-small text-medium-emphasis mt-4">
          {{ t('auth.firstAccountAdmin') }}
        </div>

        <div class="d-flex justify-center mt-4">
          <v-btn size="small" to="/sukromie" variant="text">{{ t('privacy.title') }}</v-btn>
        </div>

        <v-alert
          v-if="cookieNote"
          class="mt-3"
          closable
          density="compact"
          variant="tonal"
          @click:close="closeNote"
        >
          <span class="text-body-small">{{ t('privacy.cookieNote') }}</span>
        </v-alert>
      </v-card>
    </v-main>
  </v-app>
</template>
