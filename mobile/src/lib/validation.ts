const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const isEmail = (value: string) => EMAIL_RE.test(value.trim());
export const isPassword = (value: string) => value.length >= 8 && value.length <= 128;
