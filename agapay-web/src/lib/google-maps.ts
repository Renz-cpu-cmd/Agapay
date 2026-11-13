import { importLibrary, setOptions } from "@googlemaps/js-api-loader";

type MapLibraries = {
  maps: google.maps.MapsLibrary;
  core: google.maps.CoreLibrary;
  marker: google.maps.MarkerLibrary;
};

type Map3DLibraries = {
  maps3d: google.maps.Maps3DLibrary;
  marker: google.maps.MarkerLibrary;
};

let configuredKey = "";
let mapLibrariesPromise: Promise<MapLibraries> | null = null;
let map3DLibrariesPromise: Promise<Map3DLibraries> | null = null;

function configureGoogleMaps(apiKey: string) {
  if (configuredKey) return;
  if (typeof window !== "undefined") {
    const runtimeGoogle = (window as unknown as { google?: { maps?: { importLibrary?: unknown } } }).google;
    if (typeof runtimeGoogle?.maps?.importLibrary === "function") {
      configuredKey = apiKey;
      return;
    }
  }
  setOptions({ key: apiKey, v: "weekly", language: "en", region: "PH", authReferrerPolicy: "origin" });
  configuredKey = apiKey;
}

export function loadGoogleMapLibraries(apiKey: string): Promise<MapLibraries> {
  configureGoogleMaps(apiKey);
  if (!mapLibrariesPromise) {
    mapLibrariesPromise = Promise.all([
      importLibrary("maps"),
      importLibrary("core"),
      importLibrary("marker"),
    ]).then(([maps, core, marker]) => ({ maps, core, marker }))
      .catch(error => {
        mapLibrariesPromise = null;
        throw error;
      });
  }
  return mapLibrariesPromise;
}

export function loadGoogle3DLibraries(apiKey: string): Promise<Map3DLibraries> {
  configureGoogleMaps(apiKey);
  if (!map3DLibrariesPromise) {
    map3DLibrariesPromise = Promise.all([
      importLibrary("maps3d"),
      importLibrary("marker"),
    ]).then(([maps3d, marker]) => ({ maps3d, marker }))
      .catch(error => {
        map3DLibrariesPromise = null;
        throw error;
      });
  }
  return map3DLibrariesPromise;
}
