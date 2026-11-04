// Remotion's bundler turns an imported font file into a URL string.
declare module "*.woff2" {
  const url: string;
  export default url;
}
