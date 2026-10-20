args <- commandArgs(trailingOnly = FALSE)
script <- sub("^--file=", "", args[grepl("^--file=", args)])
root <- normalizePath(file.path(dirname(script), ".."))
setwd(root)
required <- c("rmarkdown", "jsonlite", "DBI", "RSQLite", "readxl", "dplyr", "stringr",
              "lubridate", "purrr", "sf", "leaflet", "htmltools", "htmlwidgets", "tidyr")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) stop("Faltan paquetes: ", paste(missing, collapse = ", "), ". Ejecuta npm run setup:r.")
if (!rmarkdown::pandoc_available()) stop("Falta Pandoc; instala environment.yml.")

project <- jsonlite::fromJSON("config/project.json")
inputs <- Sys.getenv("RERIMSS_INPUT_DIR", "/workspace/inputs/prueba_codex")
inputs <- normalizePath(inputs, mustWork = TRUE)
db_path <- Sys.getenv("RERIMSS_DB_PATH")
if (!nzchar(db_path)) {
  candidates <- list.files(inputs, pattern = "\\.db$", full.names = TRUE, ignore.case = TRUE)
  if (length(candidates) != 1) stop("Indica una base existente con RERIMSS_DB_PATH; se esperaba un único .db en RERIMSS_INPUT_DIR.")
  db_path <- candidates[[1]]
}
db_path <- normalizePath(db_path, mustWork = TRUE)
parameters <- list(
  db_path = db_path,
  geo_path = file.path(inputs, "renales_31082026.xlsx"),
  ageb_path = file.path(inputs, "2020_1_01_A (1)/2020_1_01_A.shp"),
  censo_path = Sys.getenv("RERIMSS_CENSO_PATH", file.path(inputs, project$census_file)),
  basemap_mode = Sys.getenv("RERIMSS_BASEMAP", "carto"),
  public_mode = FALSE
)
needed <- c(parameters[c("db_path", "geo_path", "ageb_path", "censo_path")],
            lapply(c("dbf", "shx", "prj", "cpg"), function(ext) sub("shp$", ext, parameters$ageb_path)))
absent <- unlist(needed)[!file.exists(unlist(needed))]
if (length(absent)) stop("Faltan archivos de entrada: ", paste(basename(absent), collapse = ", "))
if (!parameters$basemap_mode %in% c("none", "carto")) stop("RERIMSS_BASEMAP debe ser none o carto.")

# La comprobación previa es de solo lectura y evita crear una base vacía por error.
con <- DBI::dbConnect(RSQLite::SQLite(), db_path, flags = RSQLite::SQLITE_RO)
tryCatch({
  if (DBI::dbGetQuery(con, "PRAGMA quick_check")[[1]] != "ok") stop("La base no pasó quick_check.")
  schemas <- list(
    registros = c("folio", "curp", "sexo", "causa_erc", "edo_actual", "domicilio", "nombre",
                  "apellido_paterno", "apellido_materno", "fecha_inicio", "inicio_ts", "fecha_muerte", "fecha_ultima_consulta"),
    terapias_sustitutivas = c("id", "folio", "modalidad", "inicio", "fin")
  )
  for (name in names(schemas)) {
    if (!DBI::dbExistsTable(con, name)) stop("Falta la tabla: ", name)
    columns <- setdiff(schemas[[name]], DBI::dbListFields(con, name))
    if (length(columns)) stop("Faltan columnas en ", name, ": ", paste(columns, collapse = ", "))
  }
}, finally = DBI::dbDisconnect(con))

# Compilar en staging: un error no reemplaza el último HTML correcto.
staging <- file.path(root, "build/rerimss")
dir.create(staging, recursive = TRUE, showWarnings = FALSE)
render_env <- new.env(parent = globalenv())
rmarkdown::render(
  input = file.path(root, "build/informe-web.Rmd"), output_file = "index.html",
  output_dir = staging, intermediates_dir = staging, knit_root_dir = inputs,
  params = parameters,
  output_options = list(css = file.path(root, "web/rerimss.css"), mathjax = NULL),
  envir = render_env, quiet = TRUE
)

# Referencias de R para comprobar los controles JavaScript con las mismas personas.
points <- render_env$puntos_persona
agebs <- render_env$agebs_censo
year_min <- as.integer(render_env$anio_min)
year_max <- as.integer(render_env$anio_max)
scenario <- function(metric, start, end) {
  eligible <- switch(metric,
    total = points$startYear <= end & (is.na(points$deathYear) | points$deathYear >= start),
    incidence = points$startYear >= start & points$startYear <= end,
    active = points$startYear <= end & (is.na(points$deathYear) | points$deathYear > end)
  )
  selected <- points[eligible, ]
  counts <- table(selected$CVEGEO_AGEB)
  numerators <- as.numeric(counts[match(agebs$CVEGEO_AGEB, names(counts))])
  numerators[is.na(numerators)] <- 0
  valid_pop <- is.finite(agebs$POBTOT) & agebs$POBTOT > 0
  rates <- 100000 * numerators[valid_pop] / agebs$POBTOT[valid_pop]
  list(prefix = paste0("rerimss-", metric), start = start, end = end,
       count = nrow(selected), max_rate = if (length(rates)) max(rates) else 0)
}
scenarios <- list()
for (interval in list(c(year_min, year_max), c(year_min, year_min), c(year_max, year_max))) {
  for (metric in c("total", "incidence", "active")) {
    scenarios[[length(scenarios) + 1]] <- scenario(metric, interval[[1]], interval[[2]])
  }
}
validation <- list(
  generated_at = format(Sys.time(), tz = "America/Mexico_City", usetz = TRUE),
  geo_rows = nrow(render_env$geo), valid_coordinate_rows = nrow(render_env$geo_ok),
  invalid_coordinate_rows = nrow(render_env$geo) - nrow(render_env$geo_ok),
  ageb_polygons = nrow(agebs), agebs_with_population = sum(!is.na(agebs$POBTOT)),
  agebs_without_population = sum(is.na(agebs$POBTOT)),
  temporal_people = nrow(points), people_outside_ageb = sum(!points$asignado_ageb),
  min_year = year_min, max_year = year_max, basemap = parameters$basemap_mode,
  census_file = basename(parameters$censo_path),
  agebs_with_positive_population = sum(is.finite(agebs$POBTOT) & agebs$POBTOT > 0),
  scenarios = scenarios
)
jsonlite::write_json(validation, "build/validation.json", pretty = TRUE, auto_unbox = TRUE, digits = 12)
dir.create("dist/private", recursive = TRUE, showWarnings = FALSE)
temporary <- tempfile(pattern = ".index-", tmpdir = "dist/private", fileext = ".html")
stopifnot(file.copy(file.path(staging, "index.html"), temporary, overwrite = TRUE))
if (!file.rename(temporary, "dist/private/index.html")) stop("No se pudo guardar el informe privado.")
source("r/publication.R", local = TRUE)
public_payload <- build_public_payload(points, agebs, year_min, year_max, project)
jsonlite::write_json(public_payload, "build/public-payload.json", auto_unbox = TRUE, digits = 10, null = "null", na = "null")
cat("Informe privado generado; agregados públicos preparados. Tres mapas; años ", year_min, "–", year_max, ".\n", sep = "")
cat("Geolocalizaciones válidas: ", nrow(render_env$geo_ok), "/", nrow(render_env$geo),
    ". AGEB con población: ", sum(!is.na(agebs$POBTOT)), "/", nrow(agebs), ".\n", sep = "")
