
class VerticalBarChart extends BarChart{
    constructor(container_name, data) {
        super(container_name, data, ({top: 30, right: 30, bottom: 30, left: 200}));
        this.init()
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
        this.color = d3.scaleOrdinal([true, false], ["steelblue", "#aaa"])
        this.x = d3.scaleLinear().range([this.margin.left, this.width - this.margin.right])
        this.x.domain([0, this.computeMaxXDomain()]);
        this.buildSVG();
    }

    init(){}

    computeMaxXDomain() {
        return Math.max.apply(Math, this.root.map(function (o) {
            return o.value;
        }));
    }

    buildSVG(){
        this.svg = this.container.append("svg")
            .attr("preserveAspectRatio", "xMinYMin meet")
            .attr("viewBox", "0 0 " + this.width + " " + this.height);
        this.svg.append("rect")
            .attr("class", "background")
            .attr("fill", "none")
            .attr("pointer-events", "all")
            .attr("width", this.width)
            .attr("height", this.height);
        this.xAxis = g => g
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${this.margin.top})`)
            .call(d3.axisTop(this.x).ticks(this.width / 80, "s"))
            .call(g => (g.selection ? g.selection() : g).select(".domain").remove())
        this.yAxis = g => g
            .attr("class", "y-axis")
            .attr("transform", `translate(${this.margin.left + 0.5},0)`)
            .call(g => g.append("line")
                .attr("stroke", "currentColor")
                .attr("y1", this.margin.top)
                .attr("y2", this.height - this.margin.bottom))
        this.svg.append("g")
            .call(this.xAxis);

        this.svg.append("g")
            .call(this.yAxis);
        this.createBar();
    }

    // Creates a set of bars for the given data node, at the specified index.
    createBar() {
        let d = this.root;
        let chart = this;

        const g = this.svg.insert("g", ".y-axis")
            .attr("transform", `translate(0,${chart.margin.top + chart.barStep * chart.barPadding})`)
            .attr("text-anchor", "end")
            .style("font", "14px sans-serif").style('fill', 'cornsilk');

        const bar = g.selectAll("g")
            .data(this.root)
            .join("g");

        bar.append("text")
            .attr("x", chart.margin.left - 6)
            .attr("y", (d,i) => chart.barStep * (1 - chart.barPadding) / 2 + chart.barStep * i)
            .attr("dy", ".35em")
            .text(d => d.name).style('fill', 'cornsilk');

        // Three function that change the tooltip when user hover / move / leave a cell
        let mouseover = function(d) {
            chart.tooltip.style("opacity", 1)
        }
        let mousemove = function(d) {
            chart.tooltip
                .html("<table><tr><td style='text-align: left;'><span style='color: dodgerblue'>Name</span>: </td>" +
                    "<td style='text-align: right;'>" + d.name + "</td></tr>" +
                    "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Amount</span>: </td>" +
                    "<td style='text-align: right;'>" + Math.round(d.value*100)/100 + "</td></tr>" +
                    "</table>")
                .style("top", (d3.event.pageY + 30)+"px")
                .style("left",(d3.event.pageX + 30)+"px")
        }
        let mouseleave = function(d) {
            chart.tooltip
                .style("opacity", 0)
        }

        bar.append("rect")
            .attr("x", this.x(0))
            .attr("y", (d,i) => chart.barStep * i)
            .attr("width", d => this.x(d.value) - this.x(0))
            .attr("height", this.barStep * (1 - this.barPadding))
            .attr("fill", "steelblue")
            .on('mouseenter', function (actual, i) {
                d3.select(this).attr('opacity', 0.5)
                bar.selectAll('#limit').remove()
                const pos_x = chart.x(actual.value)
                bar.append('line')
                    .attr('id', 'limit')
                    .attr('x1', pos_x)
                    .attr('y1', 0)
                    .attr('x2', pos_x)
                    .attr('y2', chart.height)
                    .attr('stroke', 'red')
                bar.append('text')
                    .attr('class', 'divergence')
                    .attr('x', (a) => chart.x(a.value))
                    .attr('y', (a, i) => chart.barStep * i + chart.barStep * (1 - chart.barPadding) * 2 /3)
                    .attr('fill', 'white')
                    .attr('text-anchor', 'right')
                    .text((a, idx) => {
                        const divergence = ((a.value - actual.value)/actual.value * 100).toFixed(1)
                        let text = ''
                        if (divergence > 0) text += '+'
                        text += `${divergence}%`
                        return idx !== i ? text : '';
                    })
            })
            .on('mouseover', mouseover)
            .on('mouseleave', function (actual, i) {
                d3.select(this).attr('opacity', 1)
                bar.selectAll('#limit').remove()
                bar.selectAll('.divergence').remove()
                mouseleave(actual);
            })
            .on('mousemove',mousemove);

        return g;
    }

    getHeight(){
        return this.root.length * this.barStep + this.margin.top + this.margin.bottom;
    }
}

