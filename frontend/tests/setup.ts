import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom does not implement the observers and media queries used by the canvas
// and the card's reduced-motion support.
if (!('ResizeObserver' in globalThis)) {
  class ResizeObserverMock implements ResizeObserver {
    private readonly callback: ResizeObserverCallback

    constructor(callback: ResizeObserverCallback) {
      this.callback = callback
    }

    observe(target: Element) {
      // React Flow measures observed nodes from their offset dimensions.
      this.callback([{ target } as ResizeObserverEntry], this)
    }

    unobserve() {}
    disconnect() {}
  }

  globalThis.ResizeObserver = ResizeObserverMock
}

// jsdom reports zero layout for every element. Give React Flow nodes a stable
// size so they are visible and testable.
const NODE_WIDTH = 240
const NODE_HEIGHT = 200

Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
  configurable: true,
  get(this: HTMLElement) {
    return this.classList.contains('react-flow__node') ? NODE_WIDTH : 0
  },
})

Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
  configurable: true,
  get(this: HTMLElement) {
    return this.classList.contains('react-flow__node') ? NODE_HEIGHT : 0
  },
})

if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}

if (!('DOMMatrixReadOnly' in globalThis)) {
  class DOMMatrixReadOnlyMock {
    m22 = 1
  }

  // @ts-expect-error jsdom polyfill for d3-zoom
  globalThis.DOMMatrixReadOnly = DOMMatrixReadOnlyMock
}

afterEach(() => {
  cleanup()
})
