export const pageVariants = {
  enter: { opacity: 0, y: 24 },
  center: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
  },
  exit: {
    opacity: 0,
    transition: { duration: 0.1 },
  },
}

export const staggerContainer = {
  center: {
    transition: { staggerChildren: 0.06 },
  },
}

export const fadeUp = {
  enter: { opacity: 0, y: 16 },
  center: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
}

export const fadeIn = {
  enter: { opacity: 0 },
  center: {
    opacity: 1,
    transition: { duration: 0.5 },
  },
}

export const scaleIn = {
  enter: { opacity: 0, scale: 0.95 },
  center: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] },
  },
}
