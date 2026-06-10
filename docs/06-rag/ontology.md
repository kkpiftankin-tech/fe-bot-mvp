# Онтология

Закрытые словари концепций, на которые опираются metadata-фильтры. Менять онтологию = менять контракт; требует ADR.

## domain

```text
naval         — морская тематика (radar/sonar/AIS/...)
air           — воздушная
ground        — наземная
cyber         — кибер-домен
analytical    — общая аналитика без жёсткой физической привязки
custom        — открытая категория для пользовательских доменов (review_required)
```

## data_source

```text
radar
sonar
AIS
ESM
EO_IR
satellite
tracks_fused
external_conditions
tactical_objects
SQL
CSV
JSON
custom
```

## task_type

```text
classification
regression
clustering
anomaly_detection
ranking
trajectory_forecasting
object_detection
```

## data_type

```text
tabular
time_series
image
tensor
graph
event_log
mixed
```

## feature_family

```text
kinematic                 # range, speed, course, ...
rcs                       # radar cross-section
signal_quality            # snr, dynamics
acoustic                  # sonar-derived
electro_optical
sensor_analytics          # uptime, false_alarm_rate, ...
weapon_analytics
comms_analytics
object_state
environment
threat
custom
```

## phase

См. [../04-domain/value-objects.md#phase](../04-domain/value-objects.md).

## doc_type

См. [document-types.md](document-types.md).

## Управление онтологией

- Все словари — закрытые. Расширения требуют ADR.
- Каждое новое значение появляется сначала в этой странице, затем в `validators/rag_metadata_validator.py`, затем используется в карточках.
- Значение `custom` разрешено только для `domain` и `data_source`; такие карточки помечаются `requires_review=true` до явного промоушена.

## Связанные документы

- [metadata-schema.md](metadata-schema.md)
- [document-types.md](document-types.md)
- [../04-domain/value-objects.md](../04-domain/value-objects.md)
