from pathlib import Path
from datetime import datetime

import pandas as pd
import geopandas as gpd

from rapidfuzz import process

# =========================
# BASE DIRECTORY
# =========================

BASE_DIR = Path(__file__).resolve().parent

# =========================
# FOLDER PATH
# =========================

kml_awal_folder = (
    BASE_DIR
    / "input"
    / "kml_awal_shift"
)

kml_akhir_folder = (
    BASE_DIR
    / "input"
    / "kml_akhir_shift"
)

# =========================
# SHP PATH
# =========================

polygon_file = (
    BASE_DIR
    / "input"
    / "shp"
    / "area_kerja.shp"
)

# =========================
# REFERENCE FILE
# =========================

reference_unit_file = (
    BASE_DIR
    / "input"
    / "reference"
    / "master_reference_unit.xlsx"
)

reference_activity_file = (
    BASE_DIR
    / "input"
    / "reference"
    / "master_reference_activity.xlsx"
)

reference_category_file = (
    BASE_DIR
    / "input"
    / "reference"
    / "master_reference_category.xlsx"
)

reference_workingarea_file = (
    BASE_DIR
    / "input"
    / "reference"
    / "master_reference_workingarea.xlsx"
)

reference_equipment_file = (
    BASE_DIR
    / "input"
    / "reference"
    / "master_reference_equipment.xlsx"
)

# =========================
# SHIFT CONFIG
# =========================

SHIFT_CONFIG = {

    "1": {

        "kml_awal_shift": {
            "awal": "06:15",
            "akhir": "12:00"
        },

        "kml_akhir_shift": {
            "awal": "13:00",
            "akhir": "17:45"
        }
    },

    "2": {

        "kml_awal_shift": {
            "awal": "18:15",
            "akhir": "00:00"
        },

        "kml_akhir_shift": {
            "awal": "01:00",
            "akhir": "05:45"
        }
    }
}

# =========================
# AUTO DETECT KML
# =========================

def get_single_kml(folder_path):

    kml_files = list(
        folder_path.glob("*.kml")
    )

    if len(kml_files) == 0:

        raise Exception(
            f"\nTidak ada file KML di folder:\n{folder_path}"
        )

    if len(kml_files) > 1:

        raise Exception(
            f"\nFile KML lebih dari 1 di folder:\n{folder_path}"
        )

    return kml_files[0]

# =========================
# HITUNG JAM
# =========================

def calculate_hours(
    start_time_str,
    end_time_str
):

    start_time = datetime.strptime(
        start_time_str,
        "%H:%M"
    )

    end_time = datetime.strptime(
        end_time_str,
        "%H:%M"
    )

    if end_time < start_time:

        end_time = end_time.replace(
            day=end_time.day + 1
        )

    duration = (
        end_time - start_time
    ).total_seconds() / 3600

    return round(duration, 2)

# =========================
# FORMAT NUMBER
# =========================

def format_number(value):

    value = str(value).strip()

    if len(value) == 1:
        return "00" + value

    elif len(value) == 2:
        return "0" + value

    elif len(value) == 3:
        return value

    elif len(value) >= 4:
        return value[-3:]

    return value

# =========================
# CLEAN SPLIT 4
# =========================

def clean_split_4(value):

    if pd.isna(value):
        return ""

    original_value = str(value).strip()

    lower_value = original_value.lower()

    if lower_value == "b":
        return "BD"

    if lower_value == "y":
        return "NR"

    valid_map = {
        "bd": "BD",
        "r": "R",
        "nr": "NR",
        "nj": "NJ"
    }

    if lower_value in valid_map:
        return valid_map[lower_value]

    return original_value

# =========================
# FUZZY LOOKUP
# =========================

def fuzzy_lookup(
    lookup_value,
    reference_df,
    reference_key_col,
    reference_value_col,
    threshold=90
):

    exact_match = reference_df[
        reference_df[reference_key_col]
        .astype(str)
        .str.strip()
        ==
        str(lookup_value).strip()
    ]

    if not exact_match.empty:

        return exact_match.iloc[0][
            reference_value_col
        ]

    choices = reference_df[
        reference_key_col
    ].astype(str).tolist()

    result = process.extractOne(
        str(lookup_value),
        choices
    )

    if result is not None:

        best_match = result[0]
        similarity_score = result[1]

        if similarity_score >= threshold:

            matched_row = reference_df[
                reference_df[reference_key_col]
                .astype(str)
                ==
                str(best_match)
            ]

            if not matched_row.empty:

                return matched_row.iloc[0][
                    reference_value_col
                ]

    return "NOT FOUND"

# =========================
# PRIORITY ACTIVITY
# =========================

def prioritize_activity(df):

    df = df.copy()

    # =========================
    # CREATE PRIORITY
    # =========================

    df["priority"] = (
        df["Item Category"]
        .astype(str)
        .str.upper()
        .apply(

            lambda x:

            1 if " R " in f" {x} "
            else
            2 if "NR" in x
            else
            3 if "BD" in x
            else
            4 if "NJ" in x
            else
            999
        )
    )

    # =========================
    # SORT PRIORITY
    # =========================

    df = df.sort_values(
        by="priority"
    )

    # =========================
    # KEEP BEST PRIORITY
    # =========================

    df = df.drop_duplicates(
        subset=["Code Unit"],
        keep="first"
    )

    # =========================
    # DROP TEMP COLUMN
    # =========================

    df = df.drop(
        columns=["priority"]
    )

    return df

# =========================
# PROCESS KML
# =========================

def process_kml(
    kml_file,
    waktu_awal,
    waktu_akhir,
    jam,
    polygons,
    reference_unit,
    reference_activity,
    reference_category,
    reference_workingarea,
    reference_equipment,
    selected_shift,
    input_date
):

    print("\n===================================")
    print(f"PROCESSING: {kml_file.name}")
    print("===================================")

    # =========================
    # READ KML
    # =========================

    points_raw = gpd.read_file(
        kml_file,
        driver="KML"
    )

    # =========================
    # FILTER POINT
    # =========================

    points = points_raw[
        points_raw.geometry.type == "Point"
    ].copy()

    # =========================
    # REPROJECT CRS
    # =========================

    points_projected = points.to_crs(
        polygons.crs
    )

    # =========================
    # SPATIAL JOIN
    # =========================

    joined = gpd.sjoin(
        points_projected,
        polygons,
        how="left",
        predicate="within"
    )

    # =========================
    # HANDLE OUTSIDE POLYGON
    # =========================

    outside_mask = joined[
        "Location_W"
    ].isna()

    if outside_mask.any():

        outside_points = joined[
            outside_mask
        ].copy()

        outside_points = outside_points.drop(
            columns=[
                col for col in [
                    "index_right",
                    "index_left"
                ]
                if col in outside_points.columns
            ],
            errors="ignore"
        )

        polygons_clean = polygons.drop(
            columns=[
                col for col in [
                    "index_right",
                    "index_left"
                ]
                if col in polygons.columns
            ],
            errors="ignore"
        )

        nearest = gpd.sjoin_nearest(
            outside_points,
            polygons_clean,
            how="left",
            distance_col="distance",
            lsuffix="point",
            rsuffix="poly"
        )

        location_col = None

        for col in nearest.columns:

            if "Location_W" in col:
                location_col = col

        if location_col:

            joined.loc[
                outside_mask,
                "Location_W"
            ] = nearest[
                location_col
            ].values

    # =========================
    # HANDLE NULL
    # =========================

    joined["Location_W"] = (
        joined["Location_W"]
        .fillna("NOT FOUND")
    )

    # =========================
    # BASE OUTPUT
    # =========================

    output = pd.DataFrame({

        "nama_titik":
            joined["Name"],

        "Lokasi":
            joined["Location_W"]

    })

    # =========================
    # SPLIT COLUMN
    # =========================

    split_cols = output[
        "nama_titik"
    ].str.split(",", expand=True)

    split_cols.columns = [
        f"split_{i+1}"
        for i in range(split_cols.shape[1])
    ]

    # =========================
    # ENSURE REQUIRED COLUMN
    # =========================

    required_split_cols = [
        "split_1",
        "split_2",
        "split_3",
        "split_4",
        "split_5"
    ]

    for col in required_split_cols:

        if col not in split_cols.columns:

            split_cols[col] = ""

    # =========================
    # CLEAN WHITESPACE
    # =========================

    for col in required_split_cols:

        split_cols[col] = (

            split_cols[col]
                .fillna("")
                .astype(str)
                .str.strip()
        )

    # =========================
    # COMBINE BACK
    # =========================

    output = pd.concat(
        [output, split_cols],
        axis=1
    )

    # =========================
    # CLEAN SPLIT 4
    # =========================

    output["split_4_clean"] = (
        output["split_4"]
        .apply(clean_split_4)
    )

    # =========================
    # LOOKUP UNIT
    # =========================

    output["kode_lookup_unit"] = (

        output["split_1"]
            .fillna("")
            .astype(str)
            .str[:3]

        +

        output["split_2"]
            .fillna("")
            .astype(str)

        +

        output["split_3"]
            .fillna("")
            .astype(str)
            .apply(format_number)
    )

    output["Code Unit"] = (
        output["kode_lookup_unit"]
        .apply(

            lambda x: fuzzy_lookup(
                lookup_value=x,
                reference_df=reference_unit,
                reference_key_col="kode_reference_unit",
                reference_value_col="hasil_lookup_unit_master"
            )
        )
    )

    # =========================
    # LOOKUP ACTIVITY
    # =========================

    output["kode_lookup_activity"] = (

        output["split_2"]
            .fillna("")
            .astype(str)

        +

        output["split_4_clean"]
            .fillna("")
            .astype(str)

        +

        output["split_5"]
            .fillna("")
            .astype(str)
    )

    output["Item Category"] = (
        output["kode_lookup_activity"]
        .apply(

            lambda x: fuzzy_lookup(
                lookup_value=x,
                reference_df=reference_activity,
                reference_key_col="kode_reference_activity",
                reference_value_col="hasil_lookup_activity_master"
            )
        )
    )

    # =========================
    # LOOKUP CATEGORY
    # =========================

    output["Category"] = (
        output["Item Category"]
        .apply(

            lambda x: fuzzy_lookup(
                lookup_value=x,
                reference_df=reference_category,
                reference_key_col="category_key",
                reference_value_col="category_value"
            )
        )
    )

    # =========================
    # LOOKUP WORKING AREA
    # =========================

    output["Working Area"] = (
        output["Lokasi"]
        .apply(

            lambda x: fuzzy_lookup(
                lookup_value=x,
                reference_df=reference_workingarea,
                reference_key_col="workingarea_key",
                reference_value_col="workingarea_value"
            )
        )
    )

    # =========================
    # LOOKUP EQUIPMENT
    # =========================

    output["Equipment"] = (
        output["Code Unit"]
        .apply(

            lambda x: fuzzy_lookup(
                lookup_value=x,
                reference_df=reference_equipment,
                reference_key_col="equipment_key",
                reference_value_col="equipment_value"
            )
        )
    )

    # =========================
    # FINAL OUTPUT TEMPLATE
    # =========================

    final_output = pd.DataFrame({

        "Date": input_date,

        "Code Unit":
            output["Code Unit"],

        "Category":
            output["Category"],

        "Item Category":
            output["Item Category"],

        "Awal":
            waktu_awal,

        "Akhir":
            waktu_akhir,

        "Jam":
            jam,

        "Working Area":
            output["Working Area"],

        "Working Section": "",

        "Remarks / Keterangan": "",

        "Shift":
            f"Shift {selected_shift}",

        "Equipment":
            output["Equipment"],

        "Time": "",

        "Lokasi":
            output["Lokasi"],

        "Material": "",

        "Category BD": "",

        "Cut Off Report": "",

        "Class Unit": "",

        "ABC - CC": "",

        "CEK LAPORAN": "",

        "Breakdown": "",

        "Standby": "",

        "Working": ""

    })

    print(
        f"Total titik: {len(final_output)}"
    )

    return final_output

# =========================
# BALANCE SHIFT DATA
# =========================

def balance_shift_data(
    df_awal,
    df_akhir,
    awal_shift_akhir,
    akhir_shift_akhir,
    jam_shift_akhir,
    awal_shift_awal,
    akhir_shift_awal,
    jam_shift_awal
):

    unit_awal = set(
        df_awal["Code Unit"]
    )

    unit_akhir = set(
        df_akhir["Code Unit"]
    )

    missing_di_akhir = (
        unit_awal - unit_akhir
    )

    missing_di_awal = (
        unit_akhir - unit_awal
    )

    # =========================
    # COPY KE AKHIR
    # =========================

    additional_akhir = []

    for unit in missing_di_akhir:

        temp = df_awal[
            df_awal["Code Unit"] == unit
        ].copy()

        temp["Awal"] = awal_shift_akhir
        temp["Akhir"] = akhir_shift_akhir
        temp["Jam"] = jam_shift_akhir

        additional_akhir.append(temp)

    if len(additional_akhir) > 0:

        df_akhir = pd.concat(
            [df_akhir] + additional_akhir,
            ignore_index=True
        )

    # =========================
    # COPY KE AWAL
    # =========================

    additional_awal = []

    for unit in missing_di_awal:

        temp = df_akhir[
            df_akhir["Code Unit"] == unit
        ].copy()

        temp["Awal"] = awal_shift_awal
        temp["Akhir"] = akhir_shift_awal
        temp["Jam"] = jam_shift_awal

        additional_awal.append(temp)

    if len(additional_awal) > 0:

        df_awal = pd.concat(
            [df_awal] + additional_awal,
            ignore_index=True
        )

    return df_awal, df_akhir

# =========================
# GENERATE SYSTEM ACTIVITY
# =========================

def generate_system_activity(
    final_output,
    selected_shift,
    reference_category,
    input_date
):

    unique_units = final_output[
        "Code Unit"
    ].dropna().unique()

    if selected_shift == "1":

        activities = [

            {
                "item_category": "Shift Change",
                "awal": "06:00",
                "akhir": "06:15"
            },

            {
                "item_category": "Meal & Rest",
                "awal": "12:00",
                "akhir": "13:00"
            },

            {
                "item_category": "Shift Change",
                "awal": "17:45",
                "akhir": "18:00"
            }
        ]

    else:

        activities = [

            {
                "item_category": "Shift Change",
                "awal": "18:00",
                "akhir": "18:15"
            },

            {
                "item_category": "Meal & Rest",
                "awal": "00:00",
                "akhir": "01:00"
            },

            {
                "item_category": "Shift Change",
                "awal": "05:45",
                "akhir": "06:00"
            }
        ]

    generated_rows = []

    for unit in unique_units:

        sample_row = final_output[
            final_output["Code Unit"] == unit
        ].iloc[0]

        for activity in activities:

            jam = calculate_hours(
                activity["awal"],
                activity["akhir"]
            )

            generated_rows.append({

                "Date": input_date,

                "Code Unit":
                    unit,

                "Category":
                    fuzzy_lookup(
                        lookup_value=activity["item_category"],
                        reference_df=reference_category,
                        reference_key_col="category_key",
                        reference_value_col="category_value"
                    ),

                "Item Category":
                    activity["item_category"],

                "Awal":
                    activity["awal"],

                "Akhir":
                    activity["akhir"],

                "Jam":
                    jam,

                "Working Area":
                    sample_row["Working Area"],

                "Working Section": "",

                "Remarks / Keterangan": "",

                "Shift":
                    sample_row["Shift"],

                "Equipment":
                    sample_row["Equipment"],

                "Time": "",

                "Lokasi":
                    sample_row["Lokasi"],

                "Material": "",

                "Category BD": "",

                "Cut Off Report": "",

                "Class Unit": "",

                "ABC - CC": "",

                "CEK LAPORAN": "",

                "Breakdown": "",

                "Standby": "",

                "Working": ""

            })

    generated_df = pd.DataFrame(
        generated_rows
    )

    combined_output = pd.concat(
        [
            final_output,
            generated_df
        ],
        ignore_index=True
    )

    return combined_output

# =========================
# READ SHP
# =========================

polygons = gpd.read_file(
    polygon_file
)

# =========================
# READ REFERENCE
# =========================

reference_unit = pd.read_excel(
    reference_unit_file
)

reference_unit.columns = [
    "kode_reference_unit",
    "hasil_lookup_unit_master"
]

reference_activity = pd.read_excel(
    reference_activity_file
)

reference_activity.columns = [
    "kode_reference_activity",
    "hasil_lookup_activity_master"
]

reference_category = pd.read_excel(
    reference_category_file
)

reference_category.columns = [
    "category_key",
    "category_value"
]

reference_workingarea = pd.read_excel(
    reference_workingarea_file
)

reference_workingarea.columns = [
    "workingarea_key",
    "workingarea_value"
]

reference_equipment = pd.read_excel(
    reference_equipment_file
)

reference_equipment.columns = [
    "equipment_key",
    "equipment_value"
]

# =========================
# AUTO DETECT FILE
# =========================

kml_awal_file = get_single_kml(
    kml_awal_folder
)

kml_akhir_file = get_single_kml(
    kml_akhir_folder
)

# =========================
# INPUT DATE
# =========================

print("\n===================================")
print("INPUT TANGGAL REPORT")
print("===================================")

input_date = input(
    "\nMasukkan tanggal report (YYYY-MM-DD): "
)

while True:

    try:

        datetime.strptime(
            input_date,
            "%Y-%m-%d"
        )

        break

    except ValueError:

        print("\nFormat tanggal salah!")

        input_date = input(
            "Masukkan tanggal report (YYYY-MM-DD): "
        )

# =========================
# SHIFT SELECTION
# =========================

print("\n===================================")
print("PILIH SHIFT")
print("===================================")
print("1. Shift 1")
print("2. Shift 2")

selected_shift = input(
    "\nMasukkan pilihan shift (1/2): "
)

while selected_shift not in ["1", "2"]:

    print("\nShift tidak valid!")

    selected_shift = input(
        "Masukkan pilihan shift (1/2): "
    )

# =========================
# SHIFT CONFIG
# =========================

shift_data = SHIFT_CONFIG[
    selected_shift
]

# =========================
# SHIFT AWAL
# =========================

awal_shift_awal = shift_data[
    "kml_awal_shift"
]["awal"]

akhir_shift_awal = shift_data[
    "kml_awal_shift"
]["akhir"]

jam_shift_awal = calculate_hours(
    awal_shift_awal,
    akhir_shift_awal
)

# =========================
# SHIFT AKHIR
# =========================

awal_shift_akhir = shift_data[
    "kml_akhir_shift"
]["awal"]

akhir_shift_akhir = shift_data[
    "kml_akhir_shift"
]["akhir"]

jam_shift_akhir = calculate_hours(
    awal_shift_akhir,
    akhir_shift_akhir
)

# =========================
# PROCESS KML AWAL
# =========================

df_awal = process_kml(
    kml_file=kml_awal_file,
    waktu_awal=awal_shift_awal,
    waktu_akhir=akhir_shift_awal,
    jam=jam_shift_awal,
    polygons=polygons,
    reference_unit=reference_unit,
    reference_activity=reference_activity,
    reference_category=reference_category,
    reference_workingarea=reference_workingarea,
    reference_equipment=reference_equipment,
    selected_shift=selected_shift,
    input_date=input_date
)

# =========================
# PROCESS KML AKHIR
# =========================

df_akhir = process_kml(
    kml_file=kml_akhir_file,
    waktu_awal=awal_shift_akhir,
    waktu_akhir=akhir_shift_akhir,
    jam=jam_shift_akhir,
    polygons=polygons,
    reference_unit=reference_unit,
    reference_activity=reference_activity,
    reference_category=reference_category,
    reference_workingarea=reference_workingarea,
    reference_equipment=reference_equipment,
    selected_shift=selected_shift,
    input_date=input_date
)

# =========================
# PRIORITIZE ACTIVITY
# =========================

df_awal = prioritize_activity(
    df_awal
)

df_akhir = prioritize_activity(
    df_akhir
)

# =========================
# BALANCE SHIFT DATA
# =========================

df_awal, df_akhir = balance_shift_data(
    df_awal=df_awal,
    df_akhir=df_akhir,
    awal_shift_akhir=awal_shift_akhir,
    akhir_shift_akhir=akhir_shift_akhir,
    jam_shift_akhir=jam_shift_akhir,
    awal_shift_awal=awal_shift_awal,
    akhir_shift_awal=akhir_shift_awal,
    jam_shift_awal=jam_shift_awal
)

# =========================
# REMOVE INVALID DATA
# =========================

df_awal = df_awal[
    (
        df_awal["Code Unit"]
        != "NOT FOUND"
    )
    &
    (
        df_awal["Item Category"]
        != "NOT FOUND"
    )
    &
    (
        df_awal["Lokasi"]
        != "NOT FOUND"
    )
].copy()

df_akhir = df_akhir[
    (
        df_akhir["Code Unit"]
        != "NOT FOUND"
    )
    &
    (
        df_akhir["Item Category"]
        != "NOT FOUND"
    )
    &
    (
        df_akhir["Lokasi"]
        != "NOT FOUND"
    )
].copy()

print("\n===================================")
print("FILTER INVALID DATA")
print("===================================")

print(
    f"Total data awal valid : {len(df_awal)}"
)

print(
    f"Total data akhir valid: {len(df_akhir)}"
)

# =========================
# COMBINE RESULT
# =========================

final_output = pd.concat(
    [
        df_awal,
        df_akhir
    ],
    ignore_index=True
)

# =========================
# GENERATE SYSTEM ACTIVITY
# =========================

final_output = generate_system_activity(
    final_output=final_output,
    selected_shift=selected_shift,
    reference_category=reference_category,
    input_date=input_date
)

# =========================
# CREATE OUTPUT FOLDER
# =========================

output_folder = (
    BASE_DIR
    / "output"
)

output_folder.mkdir(
    exist_ok=True
)

# =========================
# TIMESTAMP
# =========================

timestamp = datetime.now().strftime(
    "%Y%m%d%H%M%S"
)

# =========================
# OUTPUT FILE
# =========================

output_file = (
    output_folder
    / f"status_report_{timestamp}.xlsx"
)

# =========================
# EXPORT EXCEL
# =========================

final_output.to_excel(
    output_file,
    index=False
)

# =========================
# RESULT
# =========================

print("\n===================================")
print("FINAL RESULT")
print("===================================")

print(final_output.head())

print("\n===================================")
print("TOTAL DATA")
print("===================================")

print(len(final_output))

print("\n===================================")
print("EXPORT SUCCESS")
print("===================================")

print(output_file)