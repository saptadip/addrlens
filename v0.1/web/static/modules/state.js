// Shared mutable state hub. ES-module scope means we can't hoist `let`
// bindings across files the way the old IIFE did — so we expose the state
// as a single mutable object that other modules import + mutate directly.
// Everything here was a top-level `let` in the original app.js.

export const dom = {
  $q:       document.getElementById('q'),
  $f:       document.getElementById('f'),
  $out:     document.getElementById('out'),
  $amen:    document.getElementById('amen'),
  $med:     document.getElementById('med'),
  $env:     document.getElementById('env'),
  $conn:    document.getElementById('conn'),
  $others:  document.getElementById('others'),
  $status:  document.getElementById('status'),
  $tabs:    document.getElementById('tabs-row'),
};

// Per-tab render state (map + selected category). Same shape for both panels
// so every renderer/selector takes a tab id and reads its slice.
export const panels = {
  amen: {$el:dom.$amen, mapId:'map-amen', hintId:'amenHint', mapRef:null, layer:null, markers:[], selected:null},
  med:  {$el:dom.$med,  mapId:'map-med',  hintId:'medHint',  mapRef:null, layer:null, markers:[], selected:null},
};

// Others tab state — mirrors panels['amen'|'med'] shape so it plugs into
// the same tab-open handler for map init.
export const othersState = { tiles: [], byKey: {}, mapRef: null, layer: null,
                              markers: [], selected: null, prov: '' };

// Stroller form state — persists across noise re-renders within one address.
export const strollerState = {floor:'', lift:null, kwr:false};

// Everything below is a mutable scalar. Wrap in an object so imports can
// read + write through a single reference.
export const S = {
  lastCoord: null,          // {lat,lon} of last successful lookup
  amenData:  null,
  eduData:   null,
  eduLayer:  null,
  eduSelected: null,
  kitaMarkers: [],
  addressMarker: null,
  envData:   null,
  mapRef:    null,          // education-tab Leaflet
  // Spec D: dedicated Leaflet instance for the lens view
  lensMap:            null,
  lensAddressMarker:  null,
  lensMapFeaturePins: [],
  lensLastTileKey:    null,
  // connectivity tab
  connData: null, connMap: null, connLayer: null,
  connAddressMarker: null, connSelected: null,
  // fetch flags
  noiseFetching: false,
  amenFetching:  false,
  amenAttempts:  0,
  // reset stroller inputs each lookup — mirrored via strollerState.
  _toastTimer: null,
};
