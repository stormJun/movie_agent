import { http } from "./http";
import type {
  EntityData,
  EntitySearchFilter,
  EntityUpdateData,
  RelationData,
  RelationSearchFilter,
  RelationUpdateData,
} from "../types/management";

export async function getEntityTypes(): Promise<string[]> {
  const resp = await http.get<{ entity_types: string[] }>("/api/v1/entity_types");
  return resp.data.entity_types || [];
}

export async function getRelationTypes(): Promise<string[]> {
  const resp = await http.get<{ relation_types: string[] }>("/api/v1/relation_types");
  return resp.data.relation_types || [];
}

export async function searchEntities(
  filters: EntitySearchFilter,
): Promise<EntityData[]> {
  const resp = await http.post<{ entities: EntityData[] }>("/api/v1/entities/search", filters);
  return resp.data.entities || [];
}

export async function searchRelations(
  filters: RelationSearchFilter,
): Promise<RelationData[]> {
  const resp = await http.post<{ relations: RelationData[] }>(
    "/api/v1/relations/search",
    filters,
  );
  return resp.data.relations || [];
}

export async function createEntity(entity: EntityData): Promise<{ success: boolean; message?: string }> {
  const resp = await http.post<{ success: boolean; message?: string }>(
    "/api/v1/entity/create",
    entity,
  );
  return resp.data;
}

export async function updateEntity(entity: EntityUpdateData): Promise<{ success: boolean; message?: string }> {
  const resp = await http.post<{ success: boolean; message?: string }>(
    "/api/v1/entity/update",
    entity,
  );
  return resp.data;
}

export async function deleteEntity(entityId: string): Promise<{ success: boolean; message?: string }> {
  const resp = await http.post<{ success: boolean; message?: string }>(
    "/api/v1/entity/delete",
    { id: entityId },
  );
  return resp.data;
}

export async function createRelation(
  relation: RelationData,
): Promise<{ success: boolean; message?: string }> {
  const resp = await http.post<{ success: boolean; message?: string }>(
    "/api/v1/relation/create",
    relation,
  );
  return resp.data;
}

export async function updateRelation(
  relation: RelationUpdateData,
): Promise<{ success: boolean; message?: string }> {
  const resp = await http.post<{ success: boolean; message?: string }>(
    "/api/v1/relation/update",
    relation,
  );
  return resp.data;
}

export async function deleteRelation(payload: {
  source: string;
  type: string;
  target: string;
}): Promise<{ success: boolean; message?: string }> {
  const resp = await http.post<{ success: boolean; message?: string }>(
    "/api/v1/relation/delete",
    payload,
  );
  return resp.data;
}
