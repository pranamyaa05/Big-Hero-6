/* The eight accessibility examples. Shared by the 3D scene (what to build, how big, from which angle)
   and the page (names, copy, interaction chips). anchor is where the pin sits, as a fraction of the part's bounding box. */
export const EX = [
  {
    id: 'cane-tip', name: 'Cane tip', helps: 'Weak legs, walking support',
    fails: 'A smooth rubber tip slips and the cane skids.',
    prints: 'A ribbed, flared foot that grips the floor.',
    prims: ['Stabilize', 'Push'], pin: 'Grip ribs', anchor: [0.5, 0.3, 1.0], el: 22
  },
  {
    id: 'pen-grip', name: 'Chunky pen grip', helps: 'Tremor, limited dexterity',
    fails: 'A thin pen is hard to hold with a shaky or weak hand.',
    prints: 'A fat, contoured barrel with finger dimples.',
    prims: ['Grip', 'Pinch'], pin: 'Finger dimples', anchor: [1.0, 0.5, 0.5], el: 12
  },
  {
    id: 'braille-tag', name: 'Braille tag', helps: 'Blind and low vision',
    fails: 'Jars, boxes and keys all feel the same without a label you can read.',
    prints: 'A raised Braille label to tie on. This one spells SALT.',
    prims: ['Pinch', 'Pull'], pin: 'Braille cells: SALT', anchor: [0.6, 1.0, 0.5], el: 40
  },
  {
    id: 'jar-grip', name: 'Jar grip ring', helps: 'Weak hands, arthritis',
    fails: 'A smooth lid can’t be turned with weak fingers.',
    prints: 'A wide, scalloped ring that fits over the lid, so the palm can turn it.',
    prims: ['Rotate', 'Grip'], pin: 'Scalloped edge', anchor: [1.0, 0.4, 0.5], el: 34
  },
  {
    id: 'walker-glide', name: 'Walker glide', helps: 'Walkers and frames',
    fails: 'A hard, narrow tip catches on the floor and the frame jolts.',
    prints: 'A smooth, ringed glide cap with a ribbed pad.',
    prims: ['Push', 'Stabilize'], pin: 'Ribbed pad', anchor: [0.5, 1.0, 0.5], el: 28
  },
  {
    id: 'key-turner', name: 'Key turner', helps: 'Weak wrists, arthritis',
    fails: 'A small key needs a pinch and a twist the wrist can’t give.',
    prints: 'A butterfly wing with a key slot: two big grips for leverage.',
    prims: ['Rotate', 'Grip'], pin: 'Finger holes', anchor: [0.82, 0.38, 0.5], el: 30
  },
  {
    id: 'dial-marker', name: 'Tactile dial marker', helps: 'Blind and low vision',
    fails: 'Oven and radio settings can only be read by sight.',
    prints: 'A knurled ring with a pointer and raised bumps, to find a setting by touch.',
    prims: ['Rotate', 'Pinch'], pin: 'Raised pointer', anchor: [0.92, 1.0, 0.5], el: 36
  },
  {
    id: 'lever-wing', name: 'Tap lever wing', helps: 'Weak arms and grip',
    fails: 'A round tap needs a tight grip and a full twist.',
    prints: 'A tall, ridged paddle that turns the tap with a push of the forearm.',
    prims: ['Push', 'Rotate'], pin: 'Ridged paddle', anchor: [0.5, 0.68, 0.78], el: 16
  }
];
