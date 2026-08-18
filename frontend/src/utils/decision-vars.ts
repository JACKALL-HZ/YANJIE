import type { DecisionVarDefinition } from '@/api/types'

export type DecisionValues = Record<string, string | number>

export function decisionLabel(definition: DecisionVarDefinition): string {
  return definition.label
}

export function decisionHint(definition: DecisionVarDefinition): string | null {
  if (definition.value_type === 'string') return null
  if (definition.minimum != null && definition.maximum != null) {
    return `范围 ${definition.minimum} 至 ${definition.maximum}`
  }
  if (definition.minimum != null) return `不低于 ${definition.minimum}`
  if (definition.maximum != null) return `不高于 ${definition.maximum}`
  return null
}

export function createDecisionValues(definitions: DecisionVarDefinition[]): DecisionValues {
  return Object.fromEntries(
    definitions
      .filter((definition) => definition.default !== null)
      .map((definition) => [definition.name, definition.default as string | number]),
  )
}

export function toDecisionPayload(
  definitions: DecisionVarDefinition[],
  values: DecisionValues,
): DecisionValues {
  return Object.fromEntries(
    definitions.flatMap((definition) => {
      const value = values[definition.name]
      return value === '' || value == null ? [] : [[definition.name, value]]
    }),
  )
}
