import { loadFont } from '@remotion/fonts'
import { staticFile } from 'remotion'
import jakarta from '@fontsource-variable/plus-jakarta-sans/files/plus-jakarta-sans-latin-wght-normal.woff2'

// Both fonts are SIL OFL 1.1 (public/fonts/archivo-OFL.txt; Plus Jakarta Sans via Fontsource).
// loadFont() holds the render until each face is ready, so no frame is drawn with a fallback.
export const fontsReady = Promise.all([
  loadFont({
    family: 'Archivo Poster',
    url: staticFile('fonts/archivo-poster.woff2'),
    weight: '800 900',
    stretch: '62% 75%',
  }),
  loadFont({ family: 'Plus Jakarta Sans', url: jakarta, weight: '200 800' }),
])
