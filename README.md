# HA Voice Hub — Community Edition 1.0.1

**HA Voice Hub** est une intégration personnalisée pour Home Assistant qui centralise les annonces vocales dans un panneau d'administration unique.

> Le domaine technique reste `maison_alain_voice_hub` pour conserver la compatibilité avec les installations existantes. Le nom visible du projet est **HA Voice Hub**.

## Fonctionnalités

- panneau **Admin Voix** directement dans Home Assistant ;
- zones vocales logiques configurables ;
- affectation des `media_player.*` depuis l'interface ;
- zone virtuelle **Toute la maison** calculée automatiquement ;
- profils `discret`, `normal`, `important`, `critique` ;
- volume par profil et/ou par zone ;
- sélection du moteur `tts.*` ;
- gestion optionnelle de la voix/style pour les moteurs TTS compatibles ;
- règles vocales basées sur les changements d'état Home Assistant ;
- délai de confirmation et anti-répétition ;
- file d'annonces pour limiter les chevauchements ;
- restauration du volume après annonce ;
- lecteur de secours configurable ;
- service central `maison_alain_voice_hub.speak` pour les automatisations.

L'édition communautaire ne contient **aucune enceinte personnelle et aucune règle automatique active par défaut**.

## Installation manuelle

1. Sauvegardez votre Home Assistant.
2. Copiez le dossier `custom_components/maison_alain_voice_hub` dans `/config/custom_components/`.
3. Redémarrez Home Assistant.
4. Ouvrez **Paramètres → Appareils et services → Ajouter une intégration**.
5. Recherchez **HA Voice Hub**.
6. Sélectionnez un moteur `tts.*` et un `media_player.*` de secours.
7. Ouvrez **Admin Voix** dans la barre latérale.
8. Affectez vos lecteurs aux zones dans l'onglet **Enceintes**.
9. Testez sur un seul lecteur à faible volume avant d'activer des règles.

## Exemple d'automatisation

```yaml
action: maison_alain_voice_hub.speak
data:
  zone: salon
  profile: normal
  message: "La porte du garage est restée ouverte."
```

Pour d'autres exemples, voir [`docs/EXEMPLES_APPELS.yaml`](docs/EXEMPLES_APPELS.yaml).

## Carte Lovelace optionnelle

Une carte `custom:button-card` permettant d'ouvrir rapidement **Admin Voix** est fournie dans [`lovelace/VOICE_HUB_ADMIN_BUTTON.yaml`](lovelace/VOICE_HUB_ADMIN_BUTTON.yaml).

## Important

- Il s'agit d'une **custom integration non officielle** et non d'un composant Home Assistant Core.
- Le projet est actuellement prévu pour une installation manuelle.
- Ne modifiez jamais `.storage` à la main.
- La compatibilité audio dépend du moteur TTS et du `media_player` utilisé.
- Testez d'abord à faible volume sur un seul lecteur.
- Aucune règle automatique n'est activée par défaut.

## Confidentialité

La version publiée ne contient pas les enceintes, zones privées, adresses IP, comptes, notifications mobiles ou règles personnelles de l'installation d'origine. Voir [`docs/CONFIDENTIALITE.md`](docs/CONFIDENTIALITE.md).

## Version

Version actuelle : **1.0.1 — Community Edition**.

Voir [`CHANGELOG.md`](CHANGELOG.md) pour les changements.
