export interface ProductHeroProps {
  title: string;
  subtitle: string;
  features: string[];
  ctaText: string;
  primaryColor: string;
  accentColor: string;
}

export interface SocialClipProps {
  headline: string;
  points: string[];
  ctaText: string;
  primaryColor: string;
  accentColor: string;
}

export interface StatsVideoProps {
  title: string;
  stats: { label: string; value: string; numericValue: number; unit: string }[];
  source: string;
  primaryColor: string;
  accentColor: string;
}

export interface VideoProps {
  productHero: ProductHeroProps;
  socialClip: SocialClipProps;
  statsVideo: StatsVideoProps;
}
