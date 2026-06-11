/**
 * MetadataEditor (SETUP-03 / T-S03-026).
 *
 * PATCH /sources/{id}/metadata с inline edit:
 * - tags (chips multi-input)
 * - description (textarea)
 * - owner_note (input)
 *
 * Optimistic UI: после успешного PATCH React Query invalidate'ит детали.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getSourceDetails, patchSourceMetadata } from "../../api/sources";
import type { UpdateSourceMetadataRequest } from "../../api/types";

interface MetadataEditorProps {
  setupJobId: string;
  sourceDocumentId: string;
}

interface UserMetadata {
  tags?: string[];
  description?: string;
  owner_note?: string;
}

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

export function MetadataEditor({
  setupJobId,
  sourceDocumentId,
}: MetadataEditorProps): JSX.Element {
  const qc = useQueryClient();
  const detailsQuery = useQuery({
    queryKey: ["source-details", setupJobId, sourceDocumentId],
    queryFn: () => getSourceDetails(setupJobId, sourceDocumentId),
  });

  const [tagsInput, setTagsInput] = useState("");
  const [description, setDescription] = useState("");
  const [ownerNote, setOwnerNote] = useState("");

  // Initial fill из server data — только при первой загрузке.
  useEffect(() => {
    if (!detailsQuery.data) return;
    const m = (detailsQuery.data.user_metadata ?? {}) as UserMetadata;
    setTagsInput((m.tags ?? []).join(", "));
    setDescription(m.description ?? "");
    setOwnerNote(m.owner_note ?? "");
  }, [detailsQuery.data]);

  const mutation = useMutation({
    mutationFn: (patch: UpdateSourceMetadataRequest) =>
      patchSourceMetadata(setupJobId, sourceDocumentId, patch),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["source-details", setupJobId, sourceDocumentId],
      });
    },
  });

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    const patch: UpdateSourceMetadataRequest = {
      tags: parseTags(tagsInput),
      description: description || null,
      owner_note: ownerNote || null,
    };
    mutation.mutate(patch);
  };

  if (detailsQuery.isLoading)
    return <p className="text-muted">Загружаем metadata…</p>;
  if (detailsQuery.error)
    return <p className="error-text">Не удалось загрузить metadata</p>;

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="metadata-editor"
      className="form-group"
    >
      <div>
        <label htmlFor="tags-input">Tags (через запятую)</label>
        <input
          id="tags-input"
          type="text"
          value={tagsInput}
          onChange={(e) => setTagsInput(e.target.value)}
          maxLength={500}
          data-testid="tags-input"
        />
      </div>
      <div>
        <label htmlFor="desc-input">Description</label>
        <textarea
          id="desc-input"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2000}
          rows={3}
          data-testid="description-input"
        />
      </div>
      <div>
        <label htmlFor="owner-note-input">Owner note</label>
        <input
          id="owner-note-input"
          type="text"
          value={ownerNote}
          onChange={(e) => setOwnerNote(e.target.value)}
          maxLength={500}
          data-testid="owner-note-input"
        />
      </div>

      {mutation.error && (
        <div className="error-text" data-testid="metadata-error">
          {String((mutation.error as Error).message)}
        </div>
      )}
      {mutation.isSuccess && (
        <div
          className="banner banner-success"
          data-testid="metadata-success"
        >
          Metadata обновлена.
        </div>
      )}

      <div className="btn-row">
        <button
          type="submit"
          className="btn"
          disabled={mutation.isPending}
          data-testid="metadata-save"
        >
          {mutation.isPending ? "Сохраняем…" : "Сохранить"}
        </button>
      </div>
    </form>
  );
}
