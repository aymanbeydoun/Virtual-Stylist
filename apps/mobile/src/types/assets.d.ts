/** Metro resolves bundled audio assets to a numeric module id. */
declare module "*.wav" {
  const asset: number;
  export default asset;
}
