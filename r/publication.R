# Única frontera de publicación: solo salen polígonos censales y celdas agregadas.
build_public_payload <- function(points, agebs, year_min, year_max, config) {
  threshold <- as.integer(config$public_min_count)
  rounding <- as.integer(config$public_rounding_base)
  span <- as.integer(config$public_period_years)
  if (threshold < 5 || rounding < 5 || span < 5) stop("La publicación requiere umbral, redondeo y periodos de al menos cinco.")
  starts <- seq(floor(year_min / span) * span, year_max, by = span)
  periods <- lapply(starts, function(start) {
    a <- max(start, year_min)
    b <- min(start + span - 1, year_max)
    list(id = paste(a, b, sep = "-"), start = a, end = b, label = paste(a, b, sep = "–"))
  })
  # Lista cerrada de atributos geográficos públicos, sin atributos clínicos.
  safe <- agebs[, c("CVEGEO_AGEB", "AGEB_LABEL", "NOM_MUN", "NOM_LOC", "POBTOT", attr(agebs, "sf_column"))]
  names(safe)[match(c("CVEGEO_AGEB", "AGEB_LABEL", "NOM_MUN", "NOM_LOC", "POBTOT"), names(safe))] <- c("code", "ageb", "municipality", "locality", "population")
  geometry_file <- tempfile(fileext = ".geojson")
  on.exit(unlink(geometry_file), add = TRUE)
  sf::st_write(safe, geometry_file, driver = "GeoJSON", quiet = TRUE, layer_options = "COORDINATE_PRECISION=6")
  geometry <- jsonlite::fromJSON(geometry_file, simplifyVector = FALSE)
  geometry <- list(type = "FeatureCollection", features = geometry$features)
  metrics <- list(
    list(id = "total", title = "Casos totales del periodo", description = "Personas presentes en algún momento del periodo: incluye los fallecimientos ocurridos dentro del intervalo."),
    list(id = "incidence", title = "Incidencia acumulada", description = "Casos con fecha de inicio dentro del periodo. La tasa corresponde al intervalo completo y no está anualizada."),
    list(id = "active", title = "Casos activos al cierre", description = "Personas que habían iniciado y permanecían vivas al cierre del último año del periodo.")
  )
  cells <- list()
  for (metric in metrics) {
    release <- list()
    for (period in periods) {
      a <- period$start
      b <- period$end
      keep <- switch(metric$id,
        total = points$startYear <= b & (is.na(points$deathYear) | points$deathYear >= a),
        incidence = points$startYear >= a & points$startYear <= b,
        active = points$startYear <= b & (is.na(points$deathYear) | points$deathYear > b)
      )
      selected <- points[keep & !is.na(points$CVEGEO_AGEB), ]
      counts <- table(selected$CVEGEO_AGEB)
      raw <- as.numeric(counts[match(agebs$CVEGEO_AGEB, names(counts))])
      raw[is.na(raw)] <- 0
      suppressed <- raw < threshold
      published <- rounding * floor(raw / rounding + 0.5)
      published[suppressed] <- NA_real_
      rates <- ifelse(is.finite(agebs$POBTOT) & agebs$POBTOT > 0, 100000 * published / agebs$POBTOT, NA_real_)
      # No se conserva el conteo original en la salida, ni siquiera en celdas ocultas.
      release[[period$id]] <- unname(lapply(seq_len(nrow(agebs)), function(i) {
        list(code = agebs$CVEGEO_AGEB[[i]], count = published[[i]], rate = rates[[i]], suppressed = suppressed[[i]])
      }))
    }
    cells[[metric$id]] <- release
  }
  list(schema_version = 1L, territory = "Aguascalientes", min_year = year_min, max_year = year_max,
       threshold = threshold, rounding = rounding, period_years = span,
       census_agebs = nrow(agebs), positive_population_agebs = sum(is.finite(agebs$POBTOT) & agebs$POBTOT > 0),
       periods = periods, metrics = metrics, geometry = geometry, cells = cells)
}
