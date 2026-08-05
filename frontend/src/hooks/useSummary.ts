import { useQuery } from "@tanstack/react-query";
import {
  DateRangeParams,
  getByAccount,
  getByBank,
  getByCategory,
  getOverview,
  getTrends,
} from "../api/endpoints/summary";

export function useOverview(params: DateRangeParams) {
  return useQuery({
    queryKey: ["summary", "overview", params],
    queryFn: () => getOverview(params),
  });
}

export function useByCategory(params: DateRangeParams) {
  return useQuery({
    queryKey: ["summary", "by-category", params],
    queryFn: () => getByCategory(params),
  });
}

export function useByAccount(params: DateRangeParams) {
  return useQuery({
    queryKey: ["summary", "by-account", params],
    queryFn: () => getByAccount(params),
  });
}

export function useByBank(params: DateRangeParams) {
  return useQuery({
    queryKey: ["summary", "by-bank", params],
    queryFn: () => getByBank(params),
  });
}

export function useTrends(months = 6) {
  return useQuery({
    queryKey: ["summary", "trends", months],
    queryFn: () => getTrends(months),
  });
}
