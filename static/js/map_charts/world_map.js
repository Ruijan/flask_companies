class WorldMap extends BarChart{
    constructor(container_name, countries, data) {
        super(container_name, data, ({top: 30, right: 30, bottom: 30, left: 30}));
        this.countries = countries;

        this.tooltip = d3.select(this.c_name)
            .append("div")
            .style("opacity", 0)
            .attr("class", "tooltip")
            .style("position", "absolute")
            .style("background-color", "white")
            .style("border", "none")
            .style("padding", "5px")
            .style("width", "auto")
            .style("color", "black")
        var path = d3.geoPath();
        var projection = d3.geoMercator()
            .center([0,20])
            .translate([this.width / 2, this.height / 2]);

        var map = d3.map();
        this.root.forEach((d) => map.set(d.country, +d.value))
        let max_value = data.reduce((max, p) => p.value > max ? p.value : max, data[0].value);
        let colorScale = d3.scaleSequential()
            .domain([0, max_value * 1.2])
            .interpolator(d3.interpolateOranges)
            .unknown("#fff")
        this.buildSVG(path, projection, map, colorScale);
    }

    buildSVG(path, projection, map, colorScale) {
        let chart = this;

        const svg = this.container.append("svg")
            .style("display", "block")
            .attr("viewBox", [0, 0, this.width, this.height]);
        // Three function that change the tooltip when user hover / move / leave a cell
        let mouseover = function (d) {
            chart.tooltip.style("opacity", 1)
        }
        let mousemove = function (d) {
            chart.tooltip
                .html("<table><tr><td style='text-align: left;'><span style='color: dodgerblue'>Name</span>: </td>" +
                    "<td style='text-align: right;'>" + d.properties.name + "</td></tr>" +
                    "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Amount</span>: </td>" +
                    "<td style='text-align: right;'>" + Math.round(d.total * 100) / 100 + "</td></tr>" +
                    "</table>")
                .style("top", (d3.event.pageY + 30) + "px")
                .style("left", (d3.event.pageX + 30) + "px")
        }
        let mouseleave = function (d) {
            chart.tooltip
                .style("opacity", 0)
        }
        svg.append("g")
            .selectAll("path")
            .data(this.countries.features)
            .enter()
            .append("path")
            // draw each country
            .attr("d", path
                .projection(projection)
            )
            // set the color of each country
            .attr("fill", function (d) {
                d.total = map.get(d.id);
                return colorScale(d.total);
            })
            .on('mouseenter', function (actual, i) {
                d3.select(this).attr('opacity', 0.5)
            })
            .on('mouseover', mouseover)
            .on('mouseleave', function (actual, i) {
                d3.select(this).attr('opacity', 1)
                mouseleave(actual);
            })
            .on('mousemove', mousemove);
        ;
    }

    getHeight(){
        return this.width * 9 / 16;
    }
}