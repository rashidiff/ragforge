// Heuristic only: never submit-blocking, and never change the canonical text.
const secretLike = /(?:\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b|\bAIza[0-9A-Za-z_-]{30,}\b|\bBearer\s+[A-Za-z0-9._~+/=-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)/;

export function containsPotentialSecret(value: string): boolean {
  return secretLike.test(value);
}
