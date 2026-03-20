import '@testing-library/jest-dom'

const noop = () => {}
Object.defineProperty(window, 'scrollTo', { value: noop })
Object.defineProperty(window, 'matchMedia', {
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: noop,
    removeListener: noop,
    addEventListener: noop,
    removeEventListener: noop,
    dispatchEvent: () => false,
  }),
})
