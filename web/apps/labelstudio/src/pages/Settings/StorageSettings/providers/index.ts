import azureProvider from "./azure";
import gcsProvider from "./gcs";
import localFilesProvider from "./localFiles";
import redisProvider from "./redis";
import { s3Provider } from "./s3";

export const providers = {
  // Standard providers
  s3: s3Provider,
  gcs: gcsProvider,
  azure: azureProvider,
  redis: redisProvider,
  // Local provider
  localfiles: localFilesProvider,
};
