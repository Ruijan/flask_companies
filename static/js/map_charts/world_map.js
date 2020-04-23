
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
            .center([0,30])
            .translate([this.width / 2, this.height / 2]);

        var map = d3.map();
        this.root.forEach((d) => map.set(d.country, +d.value))
        let max_value = data.reduce((max, p) => p.value > max ? p.value : max, data[0].value);
        let colorScale = d3.scaleSequential()
            .domain([0, max_value * 1.2])
            .interpolator(d3.interpolateOranges)
            .unknown("#a5a5a5")
        this.buildSVG(path, projection, map, colorScale);
    }

    buildSVG(path, projection, map, colorScale) {
        let chart = this;

        this.svg = this.container.append("svg")
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
                    "<td style='text-align: right;'>" + Math.round((d.total ? d.total : 0) * 100) / 100 + "</td></tr>" +
                    "</table>")
                .style("top", (d3.event.pageY + 30) + "px")
                .style("left", (d3.event.pageX + 30) + "px")
        }
        let mouseleave = function (d) {
            chart.tooltip
                .style("opacity", 0)
        }
        this.svg.append("g")
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
        this.legend({color: colorScale})
    }

    getHeight(){
        return this.width * 9 / 16;
    }
    legend({
               color,
               title,
               tickSize = 6,
               width = 320,
               height = 44 + tickSize,
               marginTop = 18,
               marginRight = 0,
               marginBottom = 16 + tickSize,
               marginLeft = 0,
               ticks = width / 64,
               tickFormat,
               tickValues
           } = {}) {

        let tickAdjust = g => g.selectAll(".tick line").attr("y1", marginTop + marginBottom - height);
        let x;

        // Continuous
        if (color.interpolate) {
            const n = Math.min(color.domain().length, color.range().length);

            x = color.copy().rangeRound(d3.quantize(d3.interpolate(marginLeft, width - marginRight), n));

            this.svg.append("image")
                .attr("x", marginLeft)
                .attr("y", marginTop)
                .attr("width", width - marginLeft - marginRight)
                .attr("height", height - marginTop - marginBottom)
                .attr("preserveAspectRatio", "none")
                .attr("xlink:href", ramp(color.copy().domain(d3.quantize(d3.interpolate(0, 1), n))).toDataURL());
        }

        // Sequential
        else if (color.interpolator) {
            x = Object.assign(color.copy()
                    .interpolator(d3.interpolateRound(marginLeft, width - marginRight)),
                {range() { return [marginLeft, width - marginRight]; }});

            this.svg.append("image")
                .attr("x", marginLeft)
                .attr("y", marginTop)
                .attr("width", width - marginLeft - marginRight)
                .attr("height", height - marginTop - marginBottom)
                .attr("preserveAspectRatio", "none")
                .attr("xlink:href", ramp(color.interpolator()).toDataURL());

            // scaleSequentialQuantile doesn’t implement ticks or tickFormat.
            if (!x.ticks) {
                if (tickValues === undefined) {
                    const n = Math.round(ticks + 1);
                    tickValues = d3.range(n).map(i => d3.quantile(color.domain(), i / (n - 1)));
                }
                if (typeof tickFormat !== "function") {
                    tickFormat = d3.format(tickFormat === undefined ? ",f" : tickFormat);
                }
            }
        }

        this.svg.append("g")
            .attr("transform", `translate(0,${height - marginBottom})`)
            .call(d3.axisBottom(x)
                .ticks(ticks, typeof tickFormat === "string" ? tickFormat : undefined)
                .tickFormat(typeof tickFormat === "function" ? tickFormat : undefined)
                .tickSize(tickSize)
                .tickValues(tickValues))
            .call(tickAdjust)
            .call(g => g.select(".domain").remove())
            .call(g => g.append("text")
                .attr("x", marginLeft)
                .attr("y", marginTop + marginBottom - height - 6)
                .attr("fill", "currentColor")
                .attr("text-anchor", "start")
                .attr("font-weight", "bold")
                .text(title));
    }
}

function ramp(color, n = 256) {
    const canvas = document.createElement('canvas');
    canvas.width = n;
    canvas.height = 1;
    const context = canvas.getContext("2d");
    for (let i = 0; i < n; ++i) {
        context.fillStyle = color(i / (n - 1));
        context.fillRect(i, 0, 1, 1);
    }
    return canvas;
}
