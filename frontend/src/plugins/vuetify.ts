/**
 * Téma podľa dizajnu: LEGO červená ako primárna, žltá na retired
 * a upozornenia. Svetlá aj tmavá varianta, prepínač je v hlavičke.
 */

import { createVuetify } from 'vuetify'
import { en, sk } from 'vuetify/locale'
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

const light = {
  dark: false,
  colors: {
    'background': '#FAF8F7',
    'surface': '#FFFFFF',
    'surface-bright': '#FFFFFF',
    'surface-variant': '#F4F1F0',
    'on-surface-variant': '#5C5B5B',
    'primary': '#D01012',
    'on-primary': '#FFFFFF',
    'primary-container': '#FFDAD6',
    'on-primary-container': '#410004',
    'secondary': '#F5C518',
    'on-secondary': '#3A2E00',
    'secondary-container': '#FFF3C4',
    'positive': '#16714A',
    'positive-container': '#D3F0E0',
    'negative': '#B3261E',
    'negative-container': '#FFDAD6',
    'error': '#B3261E',
    'info': '#1E6FB8',
    'success': '#16714A',
    'warning': '#F5C518',
  },
  variables: {
    'border-color': '#DEDAD9',
    'border-opacity': 1,
  },
}

const dark = {
  dark: true,
  colors: {
    'background': '#131212',
    'surface': '#1B1A1A',
    'surface-bright': '#2C2A2A',
    'surface-variant': '#232222',
    'on-surface-variant': '#A9A4A3',
    'primary': '#FFB3AC',
    'on-primary': '#690006',
    'primary-container': '#93000C',
    'on-primary-container': '#FFDAD6',
    'secondary': '#F5C518',
    'on-secondary': '#3A2E00',
    'secondary-container': '#4A3B00',
    'positive': '#6BD69A',
    'positive-container': '#113827',
    'negative': '#FFB4AB',
    'negative-container': '#5C1410',
    'error': '#FFB4AB',
    'info': '#6BAEE8',
    'success': '#6BD69A',
    'warning': '#F5C518',
  },
  variables: {
    'border-color': '#3B3939',
    'border-opacity': 1,
  },
}

export default createVuetify({
  theme: {
    defaultTheme: 'light',
    themes: { light, dark },
  },
  // Kalendár a dátumové pole po slovensky: pondelok ako prvý deň, dd.mm.rrrr.
  locale: { locale: 'sk', fallback: 'en', messages: { sk, en } },
  date: { locale: { sk: 'sk-SK', en: 'en-GB' } },
  defaults: {
    VCard: { rounded: 'lg' },
    VBtn: { rounded: 'sm' },
    VTextField: { variant: 'outlined', density: 'comfortable' },
    VSelect: { variant: 'outlined', density: 'comfortable' },
    VTextarea: { variant: 'outlined', density: 'comfortable' },
    VAutocomplete: { variant: 'outlined', density: 'comfortable' },
    VCombobox: { variant: 'outlined', density: 'comfortable' },
    // Ikona kalendára vnútri poľa, aby dátum vyzeral ako ostatné polia formulára.
    VDateInput: {
      variant: 'outlined',
      density: 'comfortable',
      prependIcon: '',
      prependInnerIcon: '$calendar',
    },
  },
})

export const CHART_COLORS = {
  invested: '#9A9695',
  value: '#D01012',
  proceeds: '#16714A',
  themes: ['#D01012', '#F5C518', '#1E6FB8', '#16714A', '#9A9695', '#7B4BA8'],
}
