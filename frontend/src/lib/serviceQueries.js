import { useQuery } from "@tanstack/react-query";
import { listServiceCategories, listServices } from "@/api/backendClient";

export const serviceQueryKeys = {
  services: (language = "mr") => ["services", language],
  categories: (includeHidden = false) => ["service-categories", includeHidden],
};

export function usePublishedServices(language = "mr") {
  return useQuery({
    queryKey: serviceQueryKeys.services(language),
    queryFn: () => listServices(language),
    staleTime: 30_000,
  });
}

export function useServiceCategories(includeHidden = false) {
  return useQuery({
    queryKey: serviceQueryKeys.categories(includeHidden),
    queryFn: () => listServiceCategories(includeHidden),
    staleTime: 30_000,
  });
}
