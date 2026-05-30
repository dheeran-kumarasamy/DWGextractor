#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "libdwgr.h"

class EntityTypeCounter : public DRW_Interface {
public:
    struct EntityRow {
        duint32 handle;
        std::string type;
        std::string layer;
    };

    std::map<std::string, int> counts;
    std::map<std::string, int> layerCounts;
    std::set<std::string> allLayers;
    std::vector<EntityRow> rows;
    int total = 0;

    void trackEntity(const DRW_Entity &entity, const std::string &name) {
        ++counts[name];
        ++layerCounts[entity.layer];
        allLayers.insert(entity.layer);
        rows.push_back({entity.handle, name, entity.layer});
        ++total;
    }

    void addHeader(const DRW_Header *) override {}
    void addLType(const DRW_LType &) override {}
    void addLayer(const DRW_Layer &layer) override { allLayers.insert(layer.name); }
    void addDimStyle(const DRW_Dimstyle &) override {}
    void addVport(const DRW_Vport &) override {}
    void addTextStyle(const DRW_Textstyle &) override {}
    void addAppId(const DRW_AppId &) override {}

    void addBlock(const DRW_Block &) override {}
    void setBlock(const int) override {}
    void endBlock() override {}

    void addPoint(const DRW_Point &e) override { trackEntity(e, "POINT"); }
    void addLine(const DRW_Line &e) override { trackEntity(e, "LINE"); }
    void addRay(const DRW_Ray &e) override { trackEntity(e, "RAY"); }
    void addXline(const DRW_Xline &e) override { trackEntity(e, "XLINE"); }
    void addArc(const DRW_Arc &e) override { trackEntity(e, "ARC"); }
    void addCircle(const DRW_Circle &e) override { trackEntity(e, "CIRCLE"); }
    void addEllipse(const DRW_Ellipse &e) override { trackEntity(e, "ELLIPSE"); }
    void addLWPolyline(const DRW_LWPolyline &e) override { trackEntity(e, "LWPOLYLINE"); }
    void addPolyline(const DRW_Polyline &e) override { trackEntity(e, "POLYLINE"); }
    void addSpline(const DRW_Spline *e) override { trackEntity(*e, "SPLINE"); }
    void addKnot(const DRW_Entity &) override {}
    void addInsert(const DRW_Insert &i) override {
        trackEntity(i, "INSERT");
        for (const auto &a : i.attlist) {
            if (a != nullptr) {
                trackEntity(*a, a->eType == DRW::ATTDEF ? "ATTDEF" : "ATTRIB");
            }
        }
    }
    void addTrace(const DRW_Trace &e) override { trackEntity(e, "TRACE"); }
    void add3dFace(const DRW_3Dface &e) override { trackEntity(e, "3DFACE"); }
    void addSolid(const DRW_Solid &e) override { trackEntity(e, "SOLID"); }
    void addMText(const DRW_MText &e) override { trackEntity(e, "MTEXT"); }
    void addText(const DRW_Text &e) override { trackEntity(e, "TEXT"); }
    void addDimAlign(const DRW_DimAligned *e) override { trackEntity(*e, "DIM_ALIGNED"); }
    void addDimLinear(const DRW_DimLinear *e) override { trackEntity(*e, "DIM_LINEAR"); }
    void addDimRadial(const DRW_DimRadial *e) override { trackEntity(*e, "DIM_RADIAL"); }
    void addDimDiametric(const DRW_DimDiametric *e) override { trackEntity(*e, "DIM_DIAMETRIC"); }
    void addDimAngular(const DRW_DimAngular *e) override { trackEntity(*e, "DIM_ANGULAR"); }
    void addDimAngular3P(const DRW_DimAngular3p *e) override { trackEntity(*e, "DIM_ANGULAR_3P"); }
    void addDimOrdinate(const DRW_DimOrdinate *e) override { trackEntity(*e, "DIM_ORDINATE"); }
    void addLeader(const DRW_Leader *e) override { trackEntity(*e, "LEADER"); }
    void addHatch(const DRW_Hatch *e) override { trackEntity(*e, "HATCH"); }
    void addViewport(const DRW_Viewport &e) override { trackEntity(e, "VIEWPORT"); }
    void addImage(const DRW_Image *e) override { trackEntity(*e, "IMAGE"); }
    void linkImage(const DRW_ImageDef *) override {}
    void addComment(const char *) override {}
    void addPlotSettings(const DRW_PlotSettings *) override {}

    void writeHeader(DRW_Header &) override {}
    void writeBlocks() override {}
    void writeBlockRecords() override {}
    void writeEntities() override {}
    void writeLTypes() override {}
    void writeLayers() override {}
    void writeTextstyles() override {}
    void writeVports() override {}
    void writeDimstyles() override {}
    void writeObjects() override {}
    void writeAppId() override {}
};

static void printUsage(const char *argv0) {
    std::cerr
        << "Usage: " << argv0
    << " <input.dwg> [--csv] [--entities-csv <path>] [--layers-csv <path>] [--types-csv <path>]\n";
}

static std::string csvEscape(const std::string &value) {
    bool mustQuote = false;
    std::string out;
    out.reserve(value.size() + 4);
    for (char c : value) {
        if (c == '"') {
            out.push_back('"');
            out.push_back('"');
            mustQuote = true;
        } else {
            if (c == ',' || c == '\n' || c == '\r') {
                mustQuote = true;
            }
            out.push_back(c);
        }
    }
    if (mustQuote) {
        return std::string("\"") + out + "\"";
    }
    return out;
}

static void writeTypesCsv(const EntityTypeCounter &counter, const std::string &path) {
    std::ofstream out(path);
    out << "entity_type,count\n";
    for (const auto &kv : counter.counts) {
        out << csvEscape(kv.first) << "," << kv.second << "\n";
    }
    out << "TOTAL," << counter.total << "\n";
}

static void writeEntitiesCsv(const EntityTypeCounter &counter, const std::string &path) {
    std::ofstream out(path);
    out << "handle,entity_type,layer\n";
    for (const auto &row : counter.rows) {
        out << row.handle << "," << csvEscape(row.type) << "," << csvEscape(row.layer) << "\n";
    }
}

static void writeLayersCsv(const EntityTypeCounter &counter, const std::string &path) {
    std::ofstream out(path);
    out << "layer,entity_count\n";
    for (const auto &layer : counter.allLayers) {
        const auto it = counter.layerCounts.find(layer);
        const int count = (it == counter.layerCounts.end()) ? 0 : it->second;
        out << csvEscape(layer) << "," << count << "\n";
    }
}

int main(int argc, char **argv) {
    if (argc < 2) {
        printUsage(argv[0]);
        return 1;
    }

    std::string inputPath;
    bool csv = false;
    std::string entitiesCsvPath;
    std::string layersCsvPath;
    std::string typesCsvPath;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--csv") {
            csv = true;
        } else if (arg == "--entities-csv") {
            if (i + 1 >= argc) {
                printUsage(argv[0]);
                return 1;
            }
            entitiesCsvPath = argv[++i];
        } else if (arg == "--layers-csv") {
            if (i + 1 >= argc) {
                printUsage(argv[0]);
                return 1;
            }
            layersCsvPath = argv[++i];
        } else if (arg == "--types-csv") {
            if (i + 1 >= argc) {
                printUsage(argv[0]);
                return 1;
            }
            typesCsvPath = argv[++i];
        } else if (!arg.empty() && arg[0] != '-') {
            if (!inputPath.empty()) {
                printUsage(argv[0]);
                return 1;
            }
            inputPath = arg;
        } else {
            printUsage(argv[0]);
            return 1;
        }
    }

    if (inputPath.empty()) {
        printUsage(argv[0]);
        return 1;
    }

    EntityTypeCounter counter;
    dwgRW reader(inputPath.c_str());

    if (!reader.read(&counter, true)) {
        std::cerr << "Failed to read DWG. Error code: " << static_cast<int>(reader.getError()) << "\n";
        return 2;
    }

    if (!entitiesCsvPath.empty()) {
        writeEntitiesCsv(counter, entitiesCsvPath);
    }
    if (!layersCsvPath.empty()) {
        writeLayersCsv(counter, layersCsvPath);
    }
    if (!typesCsvPath.empty()) {
        writeTypesCsv(counter, typesCsvPath);
    }

    if (csv) {
        std::cout << "entity_type,count\n";
        for (const auto &kv : counter.counts) {
            std::cout << csvEscape(kv.first) << "," << kv.second << "\n";
        }
        std::cout << "TOTAL," << counter.total << "\n";
        return 0;
    }

    std::cout << "Entity counts for: " << inputPath << "\n";
    for (const auto &kv : counter.counts) {
        std::cout << kv.first << ": " << kv.second << "\n";
    }
    std::cout << "TOTAL: " << counter.total << "\n";

    return 0;
}
