// Singleton that holds the current USD→VND rate AND display currency for use
// in non-React code (formatters.js). Updated by uiStore on startup + changes.
let _usdToVnd = 25_000
let _displayCurrency = 'USD'

export const getUsdToVnd = () => _usdToVnd
export const setUsdToVnd = (rate) => { _usdToVnd = rate }

export const getDisplayCurrency = () => _displayCurrency
export const setDisplayCurrency = (code) => { _displayCurrency = code }
