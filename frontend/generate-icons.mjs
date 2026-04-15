// One-time icon generation script — run with: node generate-icons.mjs
// Requires: npm install --save-dev sharp  (already installed)
import sharp from 'sharp';
import { writeFileSync } from 'fs';

async function makeIcon(size, outputPath) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.42;
  const fontSize = size * 0.42;

  // SVG template — dark bg, gold circle, white bold "G"
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" fill="#0a0a0a"/>
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="#C9A84C"/>
  <text
    x="${cx}"
    y="${cy}"
    font-family="Arial, Helvetica, sans-serif"
    font-weight="bold"
    font-size="${fontSize}"
    fill="white"
    text-anchor="middle"
    dominant-baseline="central"
  >G</text>
</svg>`;

  const svgBuf = Buffer.from(svg);
  await sharp(svgBuf)
    .resize(size, size)
    .png()
    .toFile(outputPath);

  console.log(`Created ${outputPath}`);
}

await makeIcon(192, 'public/icons/icon-192.png');
await makeIcon(512, 'public/icons/icon-512.png');
console.log('Icons generated successfully.');
